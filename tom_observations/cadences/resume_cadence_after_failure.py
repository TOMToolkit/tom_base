from datetime import datetime, timedelta
from dateutil.parser import parse
import json

from django import forms

from tom_observations.cadence import BaseCadenceForm, CadenceStrategy
from tom_observations.models import ObservationRecord
from tom_observations.facility import get_service_class


class ResumeCadenceAfterFailureForm(BaseCadenceForm):
    pass


class ResumeCadenceAfterFailureStrategy(CadenceStrategy):
    """The ResumeCadenceAfterFailureStrategy chooses when to submit the next observation based on the success of the
    previous observation. If the observation is successful, it submits a new one on the same cadence--that is, if the
    cadence is every three days, it will submit the next observation three days in the future. If the observations
    fails, it will submit the next observation immediately, and follow the same decision tree based on the success
    of the subsequent observation.

    This strategy requires the DynamicCadence to have a parameter ``cadence_frequency``."""

    name = 'Resume Cadence After Failure'
    description = """This strategy schedules one observation in the cadence at a time. If the observation fails, it
                     re-submits the observation until it succeeds. If it succeeds, it submits the next observation on
                     the same cadence."""
    form = ResumeCadenceAfterFailureForm

    class ResumeCadenceForm(forms.Form):
        site = forms.CharField()

    def run(self):
        last_obs = self.dynamic_cadence.observation_group.observation_records.order_by('-created').first()
        facility = get_service_class(last_obs.facility)()
        facility.update_observation_status(last_obs.observation_id)
        last_obs.refresh_from_db()
        start_keyword, end_keyword = facility.get_start_end_keywords()
        observation_payload = last_obs.parameters_as_dict
        new_observations = []
        if not last_obs.terminal:
            return
        elif last_obs.failed:
            # Submit next observation to be taken as soon as possible
            window_length = parse(observation_payload[end_keyword]) - parse(observation_payload[start_keyword])
            observation_payload[start_keyword] = datetime.now().isoformat()
            observation_payload[end_keyword] = (parse(observation_payload[start_keyword]) + window_length).isoformat()
        else:
            # Advance window normally according to cadence parameters
            observation_payload = self.advance_window(
                observation_payload, start_keyword=start_keyword, end_keyword=end_keyword
            )

        obs_type = last_obs.parameters_as_dict.get('observation_type')
        form = facility.get_form(obs_type)(observation_payload)
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
            self.dynamic_cadence.observation_group.observation_records.add(record)
            self.dynamic_cadence.observation_group.save()
            new_observations.append(record)

        for obsr in new_observations:
            facility = get_service_class(obsr.facility)()
            facility.update_observation_status(obsr.observation_id)

        return new_observations

    def advance_window(self, observation_payload, start_keyword='start', end_keyword='end'):
        # TODO: validate that cadence frequency actually exists, throw an appropriate error
        advance_window_hours = self.dynamic_cadence.cadence_parameters.get('cadence_frequency')
        new_start = parse(observation_payload[start_keyword]) + timedelta(hours=advance_window_hours)
        new_end = parse(observation_payload[end_keyword]) + timedelta(hours=advance_window_hours)
        observation_payload[start_keyword] = new_start.isoformat()
        observation_payload[end_keyword] = new_end.isoformat()

        return observation_payload
