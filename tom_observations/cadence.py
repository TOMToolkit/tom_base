from dateutil.parser import parse
from datetime import timedelta
import json

from .facility import get_service_class
from .models import ObservationRecord


class CadenceStrategy():
    def __init__(self, observation_group, *args, **kwargs):
        self.observation_group = observation_group


class RetryFailedObservationsStrategy(CadenceStrategy):
    def __init__(self, observation_group, advance_window_days, *args, **kwargs):
        self.advance_window_days = advance_window_days
        super().__init__(observation_group, *args, **kwargs)

    def run(self):
        failed_observations = [obsr for obsr in self.observation_group.observation_records.all() if obsr.failed]
        new_observations = []
        for obs in failed_observations:
            observation_payload = obs.parameters_as_dict
            observation_payload = self.advance_window(observation_payload)
            facility = get_service_class(obs.facility)()
            form = facility.get_form('IMAGING')(observation_payload)
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
                self.observation_group.observation_records.add(record)
                self.observation_group.save()
                new_observations.append(record)

        return new_observations

    def advance_window(self, observation_payload):
        new_start = parse(observation_payload['start']) + timedelta(days=self.advance_window_days)
        new_end = parse(observation_payload['end']) + timedelta(days=self.advance_window_days)
        observation_payload['start'] = new_start.isoformat()
        observation_payload['end'] = new_end.isoformat()

        return observation_payload
