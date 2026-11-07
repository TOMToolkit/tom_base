from datetime import timedelta
from dateutil.parser import parse
from django.conf import settings
import logging
from django.utils import timezone

from tom_observations.cadence import BaseCadenceForm, CadenceStrategy
from tom_observations.models import ObservationRecord
from tom_observations.facility import get_service_class

logger = logging.getLogger(__name__)


class ResumeCadenceAfterFailureForm(BaseCadenceForm):
    pass


class ResumeCadenceAfterFailureStrategy(CadenceStrategy):
    """The ResumeCadenceAfterFailureStrategy chooses when to submit the next observation based on the success of the
    previous observation. If the observation is successful, it submits a new one on the same cadence--that is, if the
    cadence is every three days, it will submit the next observation three days in the future. If the observations
    fails, it will submit the next observation immediately, and follow the same decision tree based on the success
    of the subsequent observation.

    In order to properly subclass this CadenceStrategy, one should override ``update_observation_payload``.

    This strategy requires the DynamicCadence to have a parameter ``cadence_frequency``."""

    name = 'Resume Cadence After Failure'
    description = """This strategy schedules one observation in the cadence at a time. If the observation fails, it
                     re-submits the observation until it succeeds. If it succeeds, it submits the next observation on
                     the same cadence."""
    form = ResumeCadenceAfterFailureForm

    def update_observation_payload(self, observation_payload):
        """
        :param observation_payload: form parameters for facility observation form
        :type observation_payload: dict
        """
        return observation_payload

    def run(self):
        # gets the most recent observation because the next observation is just going to modify these parameters
        last_obs = self.dynamic_cadence.observation_group.observation_records.order_by('-created').first()
        if not last_obs:
            return

        # Make a call to the facility to get the current status of the observation
        facility = get_service_class(last_obs.facility)()
        start_keyword, end_keyword = facility.get_start_end_keywords()
        facility.update_observation_status(last_obs.observation_id)  # Updates the DB record
        last_obs.refresh_from_db()  # Gets the record updates

        # Cadence logic
        # If the observation hasn't finished, do nothing
        if not last_obs.terminal:
            return

        if last_obs.status == 'CANCELED':
            self.dynamic_cadence.active = False
            self.dynamic_cadence.save()
            logger.info(f'Observation {last_obs} was canceled, stopping dynamic cadence')
            return

        # Boilerplate to get necessary properties for future calls
        observation_payload = last_obs.parameters.copy()
        scheduled_end = last_obs.scheduled_end
        if not scheduled_end:
            logger.info(f'No observation end scheduled yet, falling back to end: {observation_payload[end_keyword]}')
            scheduled_end = parse(observation_payload[end_keyword])

        if isinstance(scheduled_end, str):
            scheduled_end = parse(scheduled_end)

        if timezone.is_naive(scheduled_end):
            scheduled_end = timezone.make_aware(scheduled_end)

        observation_payload['scheduled_end'] = scheduled_end.isoformat()
        logger.info(f'Scheduled observation end: {scheduled_end}')

        if last_obs.failed:  # If the observation failed
            # Submit next observation to be taken as soon as possible with the same window length
            cadence_frequency = self.dynamic_cadence.cadence_parameters.get('cadence_frequency')
            if cadence_frequency is None:
                raise Exception(f'The {self.name} strategy requires a cadence_frequency cadence_parameter.')
            window_min = getattr(settings, 'OBS_WINDOW_MINIMUM', 24)
            window_length = min(cadence_frequency, window_min)
            now = timezone.now()
            observation_payload[start_keyword] = now.isoformat()
            observation_payload[end_keyword] = (now + timedelta(hours=window_length)).isoformat()

        else:  # If the observation succeeded
            # Advance window normally according to cadence parameters
            observation_payload = self.advance_window(
                observation_payload, start_keyword=start_keyword, end_keyword=end_keyword
            )

        observation_payload = self.update_observation_payload(observation_payload)

        # Submission of the new observation to the facility
        obs_type = last_obs.parameters.get('observation_type')
        form = facility.get_form(obs_type)(data=observation_payload)
        logger.info(f'obs payload: {observation_payload}')
        if form.is_valid():
            observation_ids = facility.submit_observation(form.observation_payload())
        else:
            logger.error(
                msg=f'Unable to submit next cadenced observation: {form.errors} '
                    f'for ObservationRecord.id: {last_obs.id}'
            )
            raise Exception(f'Unable to submit next cadenced observation: {form.errors}')

        # Creation of corresponding ObservationRecord objects for the observations
        new_observations = []
        for observation_id in observation_ids:
            # Create Observation record
            record = ObservationRecord.objects.create(
                target=last_obs.target,
                facility=facility.name,
                parameters=observation_payload,
                observation_id=observation_id
            )
            # Add ObservationRecords to the DynamicCadence
            self.dynamic_cadence.observation_group.observation_records.add(record)
            new_observations.append(record)

        self.dynamic_cadence.observation_group.save()
        # Update the status of the ObservationRecords in the DB
        for obsr in new_observations:
            facility.update_observation_status(obsr.observation_id)
            obsr.refresh_from_db()  # commit the updated observation status

        return new_observations

    def advance_window(self, observation_payload, start_keyword='start', end_keyword='end'):
        cadence_frequency = self.dynamic_cadence.cadence_parameters.get('cadence_frequency')
        if cadence_frequency is None:
            raise Exception(f'The {self.name} strategy requires a cadence_frequency cadence_parameter.')
        advance_window_hours = cadence_frequency
        window_min = getattr(settings, 'OBS_WINDOW_MINIMUM', 24)
        window_length = min(cadence_frequency, window_min)

        scheduled_end = observation_payload['scheduled_end']

        if isinstance(scheduled_end, str):
            scheduled_end = parse(scheduled_end)

        if timezone.is_naive(scheduled_end):
            scheduled_end = timezone.make_aware(scheduled_end)

        new_start = scheduled_end + timedelta(hours=advance_window_hours)
        if new_start < timezone.now():  # Ensure that the new window isn't in the past
            new_start = timezone.now()
        new_end = new_start + timedelta(hours=window_length)
        observation_payload[start_keyword] = new_start.isoformat()
        observation_payload[end_keyword] = new_end.isoformat()

        return observation_payload
