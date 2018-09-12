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
        target = Target.objects.get(pk=self.cleaned_data['target_id'])
        errors = LCOFacility.validate_observation(self, target)
        if errors:
            self.add_error(None, str(errors))
        return not errors


class LCOFacility:
    name = 'LCO'
    form = LCOObservationForm

    @classmethod
    def form_to_request(clz, form, target):
        return {
            "group_id": form.cleaned_data['group_id'],
            "proposal": form.cleaned_data['proposal'],
            "ipp_value": form.cleaned_data['ipp_value'],
            "operator": "SINGLE",
            "observation_type": form.cleaned_data['observation_type'],
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
                            "instrument_name": form.cleaned_data['instrument_name'],
                            "filter": form.cleaned_data['filter'],
                            "exposure_count": form.cleaned_data['exposure_count'],
                            "exposure_time": form.cleaned_data['exposure_time']
                        }
                    ],
                    "windows": [
                        {
                            "start": form.cleaned_data['start'],
                            "end": form.cleaned_data['end']
                        }
                    ],
                    "location": {
                        "telescope_class": "1m0"
                    },
                    "constraints": {
                        "max_airmass": form.cleaned_data['max_airmass'],
                    }
                }
            ]
        }

    @classmethod
    def submit_observation(clz, form, target):
        serialized_request = clz.form_to_request(form, target)
        response = requests.post(
            PORTAL_URL + '/api/userrequests/',
            json=serialized_request,
            headers={'Authorization': 'Token {0}'.format(LCO_SETTINGS['api_key'])}
        )
        print(response.content)
        response.raise_for_status()
        return response.json()['id']

    @classmethod
    def validate_observation(clz, form, target):
        serialized_request = clz.form_to_request(form, target)
        response = requests.post(
            PORTAL_URL + '/api/userrequests/validate/',
            json=serialized_request,
            headers={'Authorization': 'Token {0}'.format(LCO_SETTINGS['api_key'])}
        )
        print(response.content)
        response.raise_for_status()
        return response.json()['errors']
