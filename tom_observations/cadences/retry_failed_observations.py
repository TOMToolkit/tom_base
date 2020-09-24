from datetime import timedelta
from dateutil.parser import parse
import json

from tom_observations.cadence import CadenceForm, CadenceStrategy
from tom_observations.models import ObservationRecord
from tom_observations.facility import get_service_class


class RetryFailedObservationsForm(CadenceForm):
    pass


class RetryFailedObservationsStrategy(CadenceStrategy):
    """
    The RetryFailedObservationsStrategy immediately re-submits all observations within an observation group a certain
    number of hours later, as specified by ``advance_window_hours``.
    """
    name = 'Retry Failed Observations'
    description = """This strategy immediately re-submits a cadenced observation without amending any other part of the
                     cadence."""
    form = RetryFailedObservationsForm

    def __init__(self, dynamic_cadence, *args, **kwargs):
        self.advance_window_hours = kwargs.pop('advance_window_hours')
        super().__init__(dynamic_cadence, *args, **kwargs)

    def run(self):
        failed_observations = [obsr for obsr
                               in self.dynamic_cadence.observation_group.observation_records.all()
                               if obsr.failed]
        new_observations = []
        for obs in failed_observations:
            observation_payload = obs.parameters_as_dict
            facility = get_service_class(obs.facility)()
            start_keyword, end_keyword = facility.get_start_end_keywords()
            observation_payload = self.advance_window(
                observation_payload, start_keyword=start_keyword, end_keyword=end_keyword
            )
            obs_type = obs.parameters_as_dict.get('observation_type', None)
            form = facility.get_form(obs_type)(observation_payload)
            form.is_valid()
            observation_ids = facility.submit_observation(form.observation_payload())

            for observation_id in observation_ids:
                # Create Observation record
                record = ObservationRecord.objects.create(
                    target=obs.target,
                    facility=facility.name,
                    parameters=json.dumps(observation_payload),
                    observation_id=observation_id
                )
                self.dynamic_cadence.observation_group.observation_records.add(record)
                self.dynamic_cadence.observation_group.save()
                new_observations.append(record)

        return new_observations

    def advance_window(self, observation_payload, start_keyword='start', end_keyword='end'):
        new_start = parse(observation_payload[start_keyword]) + timedelta(hours=self.advance_window_hours)
        new_end = parse(observation_payload[end_keyword]) + timedelta(hours=self.advance_window_hours)
        observation_payload[start_keyword] = new_start.isoformat()
        observation_payload[end_keyword] = new_end.isoformat()

        return observation_payload
