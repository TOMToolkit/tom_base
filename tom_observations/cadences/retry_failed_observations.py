from datetime import timedelta
from dateutil.parser import parse

from tom_observations.cadence import BaseCadenceForm, CadenceStrategy
from tom_observations.models import ObservationRecord
from tom_observations.facility import get_service_class


class RetryFailedObservationsForm(BaseCadenceForm):
    pass


class RetryFailedObservationsStrategy(CadenceStrategy):
    """
    The RetryFailedObservationsStrategy immediately re-submits all observations within an observation group a certain
    number of hours later, as specified by ``advance_window_hours``.

    This strategy requires the DynamicCadence to have a parameter ``cadence_frequency``.
    """
    name = 'Retry Failed Observations'
    description = """This strategy immediately re-submits a cadenced observation without amending any other part of the
                     cadence."""
    form = RetryFailedObservationsForm

    def run(self):
        failed_observations = [obsr for obsr
                               in self.dynamic_cadence.observation_group.observation_records.all()
                               if obsr.failed]
        new_observations = []
        for obs in failed_observations:
            observation_payload = obs.parameters
            facility = get_service_class(obs.facility)()
            start_keyword, end_keyword = facility.get_start_end_keywords()
            observation_payload = self.advance_window(
                observation_payload, start_keyword=start_keyword, end_keyword=end_keyword
            )
            obs_type = obs.parameters.get('observation_type', None)
            form = facility.get_form(obs_type)(observation_payload)
            form.is_valid()
            observation_ids = facility.submit_observation(form.observation_payload())

            for observation_id in observation_ids:
                # Create Observation record
                record = ObservationRecord.objects.create(
                    target=obs.target,
                    facility=facility.name,
                    parameters=observation_payload,
                    observation_id=observation_id
                )
                self.dynamic_cadence.observation_group.observation_records.add(record)
                self.dynamic_cadence.observation_group.save()
                new_observations.append(record)

        return new_observations

    def advance_window(self, observation_payload, start_keyword='start', end_keyword='end'):
        cadence_frequency = self.dynamic_cadence.cadence_parameters.get('cadence_frequency')
        if not cadence_frequency:
            raise Exception(f'The {self.name} strategy requires a cadence_frequency cadence_parameter.')
        advance_window_hours = cadence_frequency
        new_start = parse(observation_payload[start_keyword]) + timedelta(hours=advance_window_hours)
        new_end = parse(observation_payload[end_keyword]) + timedelta(hours=advance_window_hours)
        observation_payload[start_keyword] = new_start.isoformat()
        observation_payload[end_keyword] = new_end.isoformat()

        return observation_payload
