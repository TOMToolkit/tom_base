import requests
from django.conf import settings
from django.core.exceptions import ImproperlyConfigured, ObjectDoesNotExist
from django import forms
from dateutil.parser import parse
from crispy_forms.layout import Layout, Div
from django.core.files.base import ContentFile

from tom_observations.facility import GenericObservationForm
from tom_observations.models import DataProduct, ObservationRecord
from tom_targets.models import Target

try:
    LCO_SETTINGS = settings.FACILITIES['LCO']
except AttributeError:
    LCO_SETTINGS = {
        'portal_url': 'https://observe.lco.global',
        'api_key': '',
    }

PORTAL_URL = LCO_SETTINGS['portal_url']
TERMINAL_OBSERVING_STATES = ['COMPLETED', 'CANCELED', 'WINDOW_EXPIRED']


def flatten_error_dict(form, error_dict):
    non_field_errors = []
    for k, v in error_dict.items():
        if type(v) == list:
            for i in v:
                if type(i) == str:
                    if k in form.fields:
                        form.add_error(k, i)
                    else:
                        non_field_errors.append('{}: {}'.format(k, i))
                if type(i) == dict:
                    non_field_errors.append(flatten_error_dict(form, i))
        elif type(v) == str:
            if k in form.fields:
                form.add_error(k, v)
            else:
                non_field_errors.append('{}: {}'.format(k, v))
        elif type(v) == dict:
            non_field_errors.append(flatten_error_dict(form, v))

    return non_field_errors


def get_instruments():
    response = requests.get(
        PORTAL_URL + '/api/instruments/',
        headers={'Authorization': 'Token {0}'.format(LCO_SETTINGS['api_key'])}
    )
    response.raise_for_status()
    return response.json()


def instrument_choices():
    return [(k, k) for k in get_instruments()]


def filter_choices():
    return set([(f, f) for ins in get_instruments().values() for f in ins['filters']])


def proposal_choices():
    response = requests.get(
        PORTAL_URL + '/api/profile/',
        headers={'Authorization': 'Token {0}'.format(LCO_SETTINGS['api_key'])}
    )
    response.raise_for_status()
    return [(p['id'], p['title']) for p in response.json()['proposals']]


class LCOObservationForm(GenericObservationForm):
    group_id = forms.CharField()
    proposal = forms.ChoiceField(choices=proposal_choices)
    ipp_value = forms.FloatField()
    start = forms.CharField(widget=forms.TextInput(attrs={'type': 'date'}))
    end = forms.CharField(widget=forms.TextInput(attrs={'type': 'date'}))
    filter = forms.ChoiceField(choices=filter_choices)
    instrument_name = forms.ChoiceField(choices=instrument_choices)
    exposure_count = forms.IntegerField(min_value=1)
    exposure_time = forms.FloatField(min_value=0.1)
    max_airmass = forms.FloatField()
    observation_type = forms.ChoiceField(choices=(('NORMAL', 'Normal'), ('TARGET_OF_OPPORTUNITY', 'Rapid Response')))

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.helper.layout = Layout(
            self.common_layout,
            Div(
                Div(
                    'group_id', 'proposal', 'ipp_value', 'observation_type', 'start', 'end',
                    css_class='col'
                ),
                Div(
                    'filter', 'instrument_name', 'exposure_count', 'exposure_time', 'max_airmass',
                    css_class='col'
                ),
                css_class='form-row'
            )
        )

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
            self.add_error(None, flatten_error_dict(self, errors))
        return not errors

    def instrument_to_type(self, instrument_name):
        if any(x in instrument_name for x in ['FLOYDS', 'NRES']):
            return 'SPECTRUM'
        else:
            return 'EXPOSE'

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
                            "type": self.instrument_to_type(self.cleaned_data['instrument_name']),
                            "instrument_name": self.cleaned_data['instrument_name'],
                            "filter": self.cleaned_data['filter'],
                            "spectra_slit": self.cleaned_data['filter'],
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
                        "telescope_class": self.cleaned_data['instrument_name'][:3].lower()
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
        response.raise_for_status()
        return [r['id'] for r in response.json()['requests']]

    @classmethod
    def validate_observation(clz, observation_payload):
        response = requests.post(
            PORTAL_URL + '/api/userrequests/validate/',
            json=observation_payload,
            headers={'Authorization': 'Token {0}'.format(LCO_SETTINGS['api_key'])}
        )
        response.raise_for_status()
        return response.json()['errors']

    @classmethod
    def get_observation_url(clz, observation_id):
        return PORTAL_URL + '/requests/' + observation_id

    @classmethod
    def get_terminal_observing_states(clz):
        return TERMINAL_OBSERVING_STATES

    @classmethod
    def get_observation_status(clz, observation_id):
        response = requests.get(
            PORTAL_URL + '/api/requests/{0}'.format(observation_id),
            headers={'Authorization': 'Token {0}'.format(LCO_SETTINGS['api_key'])}
        )
        response.raise_for_status()
        return response.json()['state']

    @classmethod
    def update_observing_status(clz, observation_id):
        try:
            record = ObservationRecord.objects.get(observation_id=observation_id)
            record.status = clz.get_observation_status(observation_id)
            record.save()
        except ObjectDoesNotExist:
            raise Exception('No record exists for that observation id')

    @classmethod
    def _get_archive_token(clz, request):
        if request and request.session.get('LCO_ARCHIVE_TOKEN'):
            return request.session['LCO_ARCHIVE_TOKEN']
        else:
            response = requests.get(
                PORTAL_URL + '/api/profile/',
                headers={'Authorization': 'Token {0}'.format(LCO_SETTINGS['api_key'])}
            )
            archive_token = response.json()['tokens']['archive']
            if request:
                request.session['LCO_ARCHIVE_TOKEN'] = archive_token

            return archive_token

    @classmethod
    def save_data_products(clz, observation_record, product_id=None, request=None):
        products = []
        frames = clz._archive_frames(observation_record.observation_id, product_id, request)

        for frame in frames:
            dp, created = DataProduct.objects.get_or_create(
                product_id=frame['id'],
                target=observation_record.target,
                observation_record=observation_record,
            )
            if created:
                frame_data = requests.get(frame['url']).content
                dfile = ContentFile(frame_data)
                dp.data.save(frame['filename'], dfile)
                dp.save()
            products.append(dp)
        return products

    @classmethod
    def data_products(clz, observation_record, request=None):
        products = {'saved': [], 'unsaved': []}
        for frame in clz._archive_frames(observation_record.observation_id, request=request):
            try:
                dp = DataProduct.objects.get(product_id=frame['id'])
                products['saved'].append(dp)
            except DataProduct.DoesNotExist:
                products['unsaved'].append({
                    'id': frame['id'],
                    'filename': frame['filename'],
                    'created': frame['DATE_OBS'],
                    'url': frame['url']
                })
        return products

    @classmethod
    def _archive_frames(clz, observation_id, product_id=None, request=None):
        # todo save this key somewhere
        archive_token = clz._get_archive_token(request)
        frames = []
        if product_id:
            response = requests.get(
                'https://archive-api.lco.global/frames/{0}/'.format(product_id),
                headers={'Authorization': 'Bearer {0}'.format(archive_token)}
            )
            response.raise_for_status()
            frames = [response.json()]
        else:
            response = requests.get(
                'https://archive-api.lco.global/frames/?REQNUM={0}'.format(observation_id),
                headers={'Authorization': 'Bearer {0}'.format(archive_token)}
            )
            response.raise_for_status()
            frames = response.json()['results']

        return frames
