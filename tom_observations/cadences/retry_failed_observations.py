from datetime import timedelta
from dateutil.parser import parse

from tom_observations.cadence import BaseCadenceForm, CadenceStrategy
from tom_observations.models import ObservationRecord, DynamicCadence
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
        records = self.dynamic_cadence.observation_group.observation_records.all().order_by('-created')
        last_obs = records.first()

        if not last_obs:
            return

        facility_class = get_service_class(last_obs.facility)
        facility = facility_class()
        facility.update_observation_status(last_obs.observation_id)
        last_obs.refresh_from_db()

        if not last_obs.terminal:
            return
        elif last_obs.status == 'COMPLETED':
            self.dynamic_cadence.active = False
            self.dynamic_cadence.save()
            return

        if not last_obs.failed:
            return

        observation_payload = last_obs.parameters.copy()

        start_keyword, end_keyword = facility.get_start_end_keywords()
        observation_payload = self.advance_window(
            observation_payload, start_keyword=start_keyword, end_keyword=end_keyword
        )
        
        obs_type = observation_payload.get('observation_type')
        form = facility.get_form(obs_type)(observation_payload)
        
        if not form.is_valid():
            return

        observation_ids = facility.submit_observation(form.observation_payload())
        new_observations = []
    
        for observation_id in observation_ids:
            record = ObservationRecord.objects.create(
                target=last_obs.target,
                facility=facility.name,
                parameters=observation_payload,
                observation_id=observation_id
            )
            self.dynamic_cadence.observation_group.observation_records.add(record)
            new_observations.append(record)

        self.dynamic_cadence.observation_group.save()

        for obsr in new_observations:
            facility.update_observation_status(obsr.observation_id)

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
