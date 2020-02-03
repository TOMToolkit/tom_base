from abc import ABC, abstractmethod
from importlib import import_module

from datetime import datetime, timedelta
from dateutil.parser import parse
import json

from django.conf import settings

from tom_observations.facility import get_service_class
from tom_observations.models import ObservationRecord


DEFAULT_CADENCE_STRATEGIES = [
    'tom_observations.cadence.RetryFailedObservationsStrategy',
    'tom_observations.cadence.ResumeCadenceAfterFailureStrategy'
]


def get_cadence_strategies():
    try:
        TOM_CADENCE_STRATEGIES = settings.TOM_CADENCE_STRATEGIES
    except AttributeError:
        TOM_CADENCE_STRATEGIES = DEFAULT_CADENCE_STRATEGIES

    cadence_choices = {}
    for cadence in TOM_CADENCE_STRATEGIES:
        mod_name, class_name = cadence.rsplit('.', 1)
        try:
            mod = import_module(mod_name)
            clazz = getattr(mod, class_name)
        except (ImportError, AttributeError):
            raise ImportError(f'Could not import {cadence}. Did you provide the correct path?')
        print(mod_name)
        print(class_name)
        cadence_choices[class_name] = clazz
    return cadence_choices


class CadenceStrategy(ABC):
    def __init__(self, observation_group=None, *args, **kwargs):
        self.cadence_strategy = type(self).__name__
        self.observation_group = observation_group

    @abstractmethod
    def run(self):
        pass


class RetryFailedObservationsStrategy(CadenceStrategy):
    """
    The RetryFailedObservationsStrategy immediately re-submits all observations within an observation group a certain
    number of hours later, as specified by ``advance_window_hours``.
    """

    def __init__(self, advance_window_hours, observation_group=None, *args, **kwargs):
        self.advance_window_hours = advance_window_hours
        super().__init__(observation_group, *args, **kwargs)

    def run(self):
        failed_observations = [obsr for obsr in self.observation_group.observation_records.all() if obsr.failed]
        new_observations = []
        for obs in failed_observations:
            observation_payload = obs.parameters_as_dict
            facility = get_service_class(obs.facility)()
            start_keyword, end_keyword = facility.get_start_end_keywords()
            observation_payload = self.advance_window(
                observation_payload, start_keyword=start_keyword, end_keyword=end_keyword
            )
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

    def advance_window(self, observation_payload, start_keyword='start', end_keyword='end'):
        new_start = parse(observation_payload[start_keyword]) + timedelta(hours=self.advance_window_hours)
        new_end = parse(observation_payload[end_keyword]) + timedelta(hours=self.advance_window_hours)
        observation_payload[start_keyword] = new_start.isoformat()
        observation_payload[end_keyword] = new_end.isoformat()

        return observation_payload


class ResumeCadenceAfterFailureStrategy(CadenceStrategy):
    """The ResumeCadenceAfterFailureStrategy chooses when to submit the next observation based on the success of the
    previous observation. If the observation is successful, it submits a new one on the same cadence--that is, if the
    cadence is every three days, it will submit the next observation three days in the future. If the observations
    fails, it will submit the next observation immediately, and follow the same decision tree based on the success
    of the subsequent observation."""

    def __init__(self, advance_window_hours, observation_group, *args, **kwargs):
        self.advance_window_hours = advance_window_hours
        super().__init__(observation_group, *args, **kwargs)

    def run(self):
        last_obs = self.observation_group.observation_records.order_by('-created').first()
        facility = get_service_class(last_obs.facility)()
        facility.update_observation_status(last_obs.id)
        last_obs.refresh_from_db()
        start_keyword, end_keyword = facility.get_start_end_keywords()
        observation_payload = last_obs.parameters_as_dict
        new_observations = []
        if last_obs.status not in facility.get_terminal_observing_states():
            return
        elif last_obs.status in facility.get_failed_observing_states():
            # Submit next observation to be taken as soon as possible
            window_length = parse(observation_payload['end']) - parse(observation_payload['start'])
            observation_payload['start'] = datetime.now()
            observation_payload['end'] = observation_payload['start'] + window_length
        else:
            # Advance window normally according to cadence parameters
            observation_payload = self.advance_window(
                observation_payload, start_keyword=start_keyword, end_keyword=end_keyword
            )

        form = facility.get_form('IMAGING')(observation_payload)
        form.is_valid()
        observation_ids = facility.submit_observation(form.observation_payload())

        for observation_id in observation_ids:
            # Create Observation record
            record = ObservationRecord.objects.create(
                target=last_obs.target,
                facility=facility.name,
                parameters=json.dumps(observation_payload),
                observation_id=observation_id
            )
            self.observation_group.observation_records.add(record)
            self.observation_group.save()
            new_observations.append(record)

        return new_observations

    def advance_window(self, observation_payload, start_keyword='start', end_keyword='end'):
        new_start = parse(observation_payload[start_keyword]) + timedelta(hours=self.advance_window_hours)
        new_end = parse(observation_payload[end_keyword]) + timedelta(hours=self.advance_window_hours)
        observation_payload[start_keyword] = new_start.isoformat()
        observation_payload[end_keyword] = new_end.isoformat()

        return observation_payload
