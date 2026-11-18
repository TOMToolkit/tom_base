from datetime import timedelta
from dateutil.parser import parse
import logging
from django.conf import settings
from django.utils import timezone

from tom_observations.cadence import BaseCadenceForm, CadenceStrategy
from tom_observations.models import ObservationRecord
from tom_observations.facility import get_service_class

logger = logging.getLogger(__name__)


class RetryFailedObservationsForm(BaseCadenceForm):
    pass


class BaseRetryFailedObservationsStrategy(CadenceStrategy):
    """
    The BaseRetryFailedObservationsStrategy immediately re-submits all observations within an observation
    group a certain number of hours later, as specified by ``advance_window_hours``.

    This strategy requires the DynamicCadence to have a parameter ``cadence_frequency``.
    """
    name = 'Retry Failed Observations'
    description = """This strategy immediately re-submits a cadenced observation without amending any
                     other part of the cadence."""
    form = RetryFailedObservationsForm

    def retry_observation(self, first_obs, last_obs, facility):
        '''
        Default retry observations, for BaseRetry strategy (retry until successful), the default is to always
        retry the observations until obtained
        '''
        return True

    def notify_success(self, obs):
        '''
        Function to add a call to slack or email on successful single time observations
        '''
        return

    def run(self):
        records = self.dynamic_cadence.observation_group.observation_records.all().order_by('created')
        first_obs = records.first()
        last_obs = records.last()

        if not first_obs or not last_obs:
            return

        facility = get_service_class(last_obs.facility)()
        facility.update_observation_status(last_obs.observation_id)
        last_obs.refresh_from_db()

        if not last_obs.terminal:
            return

        if last_obs.status == 'COMPLETED':
            self.dynamic_cadence.active = False
            self.dynamic_cadence.save()
            logger.info(f'Observation {last_obs} completed; turned off dynamic cadence')
            return self.notify_success(last_obs)

        if last_obs.status == 'CANCELED':
            self.dynamic_cadence.active = False
            self.dynamic_cadence.save()
            logger.info(f'Observation {last_obs} was canceled, stopping dynamic cadence')
            return

        if not self.retry_observation(first_obs, last_obs, facility):
            self.dynamic_cadence.active = False
            self.dynamic_cadence.save()
            logger.info(f'Stopping retry cadence for observation group {self.dynamic_cadence.observation_group.id}')
            return

        return self.submit_retry_observation(first_obs, last_obs, facility)

    def submit_retry_observation(self, first_obs, last_obs, facility):
        observation_payload = last_obs.parameters.copy()

        start_keyword, end_keyword = facility.get_start_end_keywords()
        observation_payload = self.advance_window(
            observation_payload, start_keyword=start_keyword, end_keyword=end_keyword,
            first_obs=first_obs, facility=facility
        )

        if observation_payload is None:
            self.dynamic_cadence.active = False
            self.dynamic_cadence.save()
            logger.info(
                f'No retry window remaining for observation group '
                f'{self.dynamic_cadence.observation_group.id}; deactivated silently'
            )
            return

        obs_type = observation_payload.get('observation_type')
        form = facility.get_form(obs_type)(data=observation_payload)

        if not form.is_valid():
            logger.error(
                msg=f'Unable to submit next observation: {form.errors} '
                f'for ObservationRecord.id: {last_obs.id}'
            )
            raise Exception(f'Unable to submit next observation: {form.errors}')

        observation_ids = facility.submit_observation(form.observation_payload())
        new_observations = []

        for observation_id in observation_ids:
            record = ObservationRecord.objects.create(
                target=last_obs.target,
                facility=facility.name,
                parameters=observation_payload,
                observation_id=observation_id,
            )
            self.dynamic_cadence.observation_group.observation_records.add(record)
            new_observations.append(record)

        self.dynamic_cadence.observation_group.save()

        for obsr in new_observations:
            facility.update_observation_status(obsr.observation_id)
            obsr.refresh_from_db()

        return new_observations

    def advance_window(self, observation_payload,
                       start_keyword='start', end_keyword='end', first_obs=None, facility=None):
        cadence_frequency = self.dynamic_cadence.cadence_parameters.get('cadence_frequency')
        if cadence_frequency is None:
            raise Exception(
                f'The {self.name} strategy requires a cadence_frequency cadence_parameter.'
            )

        window_min = getattr(settings, 'OBS_WINDOW_MINIMUM', 24)
        window_length = min(cadence_frequency, window_min)

        new_start = timezone.now()
        new_end = new_start + timedelta(hours=window_length)

        observation_payload[start_keyword] = new_start.isoformat()
        observation_payload[end_keyword] = new_end.isoformat()
        return observation_payload


class RetryFailedObservationsStrategy(BaseRetryFailedObservationsStrategy):
    """
    Retry indefinitely until the observation succeeds.
    """
    pass


class RetryUntilDeadlineStrategy(BaseRetryFailedObservationsStrategy):
    """
    Retry in short windows until either the observation succeeds, or the
    original cadence_frequency interval has elapsed.
    """

    def retry_observation(self, first_obs, last_obs, facility):
        deadline = self.get_deadline(first_obs, facility)
        return timezone.now() < deadline

    def advance_window(self, observation_payload,
                       start_keyword='start', end_keyword='end', first_obs=None, facility=None):
        cadence_frequency = self.dynamic_cadence.cadence_parameters.get('cadence_frequency')
        if cadence_frequency is None:
            raise Exception(
                f'The {self.name} strategy requires a cadence_frequency cadence_parameter.'
            )

        window_min = getattr(settings, 'OBS_WINDOW_MINIMUM', 24)
        window_length = min(cadence_frequency, window_min)

        deadline = self.get_deadline(first_obs, facility)
        new_start = timezone.now()

        if new_start >= deadline:
            return None

        new_end = min(new_start + timedelta(hours=window_length), deadline)

        if new_end <= new_start:
            return None

        observation_payload[start_keyword] = new_start.isoformat()
        observation_payload[end_keyword] = new_end.isoformat()
        return observation_payload

    def get_deadline(self, first_obs, facility):
        cadence_frequency = self.dynamic_cadence.cadence_parameters.get('cadence_frequency')
        if cadence_frequency is None:
            raise Exception(
                f'The {self.name} strategy requires a cadence_frequency cadence_parameter.'
            )

        start_keyword, _ = facility.get_start_end_keywords()
        start_value = first_obs.parameters.get(start_keyword)

        if not start_value:
            raise Exception(
                f'Could not determine original start time for '
                f'ObservationRecord.id={first_obs.id}'
            )

        original_start = parse(start_value) if isinstance(start_value, str) else start_value
        if timezone.is_naive(original_start):
            original_start = timezone.make_aware(original_start)

        return original_start + timedelta(hours=cadence_frequency)
