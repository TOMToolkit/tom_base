import requests

from django.conf import settings
from django.core.exceptions import ImproperlyConfigured
from django import forms
from dateutil.parser import parse

from tom_observations.facility import GenericObservationForm
from tom_targets.models import Target

try:
    LCO_SETTINGS = settings.FACILITIES['LCO']
except AttributeError as e:
    raise ImproperlyConfigured('Could not load LCO settings: {}'.format(e))

PORTAL_URL = 'http://valhalladev.lco.gtn'


def flatten_error_dict(error_dict):
    errors = []
    for k, v in error_dict.items():
        if type(v) == list:
            for i in v:
                if type(i) == str:
                    errors.append('{}: {}'.format(k, i))
                if type(i) == dict:
                    errors.append(flatten_error_dict(i))
        elif type(v) == str:
            errors.append('{}: {}'.format(k, v))
        elif type(v) == dict:
            errors.append(flatten_error_dict(v))

    return errors


class LCOObservationForm(GenericObservationForm):
    group_id = forms.CharField()
    proposal = forms.CharField()
    ipp_value = forms.FloatField()
    start = forms.CharField(widget=forms.TextInput(attrs={'type': 'date'}))
    end = forms.CharField(widget=forms.TextInput(attrs={'type': 'date'}))
    filter = forms.CharField()
    instrument_name = forms.CharField()
    exposure_count = forms.IntegerField(min_value=1)
    exposure_time = forms.FloatField(min_value=0.1)
    max_airmass = forms.FloatField()
    observation_type = forms.CharField()

    def clean_start(self):
        start = self.cleaned_data['start']
        return parse(start).isoformat()

    def clean_end(self):
        end = self.cleaned_data['end']
        return parse(end).isoformat()

    def is_valid(self):
        super().is_valid()
        errors = LCOFacility.validate_observation(self.observation_payload)
        if errors:
            self.add_error(None, flatten_error_dict(errors))
        return not errors

    @property
    def observation_payload(self):
        target = Target.objects.get(pk=self.cleaned_data['target_id'])
        return {
            "group_id": self.cleaned_data['group_id'],
            "proposal": self.cleaned_data['proposal'],
            "ipp_value": self.cleaned_data['ipp_value'],
            "operator": "SINGLE",
            "observation_type": self.cleaned_data['observation_type'],
            "requests": [
                {
                    "target": {
                        "name": target.name,
                        "type": target.type,
                        "ra": target.ra,
                        "dec": target.dec,
                        "proper_motion_ra": target.pm_ra,
                        "proper_motion_dec": target.pm_dec,
                        "epoch": target.epoch,
                        "orbinc": target.inclination,
                        "longascnode": target.lng_asc_node,
                        "argofperih": target.arg_of_perihelion,
                        "perihdist": target.distance,
                        "meandist": target.semimajor_axis,
                        "meananom": target.mean_anomaly,
                        "dailymot": target.mean_daily_motion
                    },
                    "molecules": [
                        {
                            "type": "EXPOSE",
                            "instrument_name": self.cleaned_data['instrument_name'],
                            "filter": self.cleaned_data['filter'],
                            "exposure_count": self.cleaned_data['exposure_count'],
                            "exposure_time": self.cleaned_data['exposure_time']
                        }
                    ],
                    "windows": [
                        {
                            "start": self.cleaned_data['start'],
                            "end": self.cleaned_data['end']
                        }
                    ],
                    "location": {
                        "telescope_class": "1m0"
                    },
                    "constraints": {
                        "max_airmass": self.cleaned_data['max_airmass'],
                    }
                }
            ]
        }


class LCOFacility:
    name = 'LCO'
    form = LCOObservationForm

    @classmethod
    def submit_observation(clz, observation_payload):
        response = requests.post(
            PORTAL_URL + '/api/userrequests/',
            json=observation_payload,
            headers={'Authorization': 'Token {0}'.format(LCO_SETTINGS['api_key'])}
        )
        print(response.content)
        response.raise_for_status()
        return response.json()['id']

    @classmethod
    def validate_observation(clz, observation_payload):
        response = requests.post(
            PORTAL_URL + '/api/userrequests/validate/',
            json=observation_payload,
            headers={'Authorization': 'Token {0}'.format(LCO_SETTINGS['api_key'])}
        )
        print(response.content)
        response.raise_for_status()
        return response.json()['errors']

    @classmethod
    def get_observation_url(clz, observation_id):
        return PORTAL_URL + '/userrequests/' + observation_id
