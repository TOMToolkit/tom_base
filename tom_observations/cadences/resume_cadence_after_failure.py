from datetime import datetime, timedelta
from dateutil.parser import parse
from django.conf import settings
import logging

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

        # Make a call to the facility to get the current status of the observation
        facility = get_service_class(last_obs.facility)()
        start_keyword, end_keyword = facility.get_start_end_keywords()
        facility.update_observation_status(last_obs.observation_id)  # Updates the DB record
        last_obs.refresh_from_db()  # Gets the record updates

        # Boilerplate to get necessary properties for future calls
        observation_payload = last_obs.parameters

        # Only needs the scheduled end from the observatory
        observation_payload['scheduled_end'] = last_obs.scheduled_end

        # Cadence logic
        # If the observation hasn't finished, do nothing
        if not last_obs.terminal:
            return
        elif last_obs.failed:  # If the observation failed
            # Submit next observation to be taken as soon as possible with the same window length
            # Make the window length the cadence frequency or 24 hours, whichever is shorter.
            cadence_frequency = self.dynamic_cadence.cadence_parameters.get('cadence_frequency')
            if not cadence_frequency:
                raise Exception(f'The {self.name} strategy requires a cadence_frequency cadence_parameter.')
            window_length = 24 if cadence_frequency > 24 else cadence_frequency
            observation_payload[start_keyword] = datetime.now().isoformat()
            observation_payload[end_keyword] = (parse(observation_payload[start_keyword]) + window_length).isoformat()
        else:  # If the observation succeeded
            # Advance window normally according to cadence parameters
            observation_payload = self.advance_window(
                observation_payload, start_keyword=start_keyword, end_keyword=end_keyword
            )

        observation_payload = self.update_observation_payload(observation_payload)

        # Submission of the new observation to the facility
        obs_type = last_obs.parameters.get('observation_type')
        form = facility.get_form(obs_type)(data=observation_payload)
        if form.is_valid():
            observation_ids = facility.submit_observation(form.observation_payload())
        else:
            logger.error(msg=f'Unable to submit next cadenced observation: {form.errors}')
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
            self.dynamic_cadence.observation_group.save()
            new_observations.append(record)

        # Update the status of the ObservationRecords in the DB
        for obsr in new_observations:
            facility = get_service_class(obsr.facility)()
            facility.update_observation_status(obsr.observation_id)
            obsr.refresh_from_db() # commit the updated observation status

        return new_observations

    def advance_window(self, observation_payload, start_keyword='start', end_keyword='end'):
        cadence_frequency = self.dynamic_cadence.cadence_parameters.get('cadence_frequency')
        if not cadence_frequency:
            raise Exception(f'The {self.name} strategy requires a cadence_frequency cadence_parameter.')
        advance_window_hours = cadence_frequency

        # Window length for the observation should be every 24 hours unless the frequency is less than 24
        # then just the cadence frequency (24 hour window defined in the settings)
        if settings.OBS_WINDOW_MINIMUM:
            min_window = settings.OBS_WINDOW_MINIMUM
        else:
            min_window = 24
        window_length = min_window if cadence_frequency > min_window else cadence_frequency

        # Define new start to be at the end of the previous observation + cadence in hours
        new_start = parse(observation_payload['scheduled_end']) + timedelta(hours=advance_window_hours)
        if new_start < datetime.now():  # Ensure that the new window isn't in the past
            new_start = datetime.now()
        new_end = new_start + window_length
        observation_payload[start_keyword] = new_start.isoformat()
        observation_payload[end_keyword] = new_end.isoformat()

        return observation_payload
