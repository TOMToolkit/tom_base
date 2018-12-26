import requests
from django.conf import settings
from django import forms
from dateutil.parser import parse
from crispy_forms.layout import Layout, Div
from django.core.cache import cache
from datetime import datetime

from tom_observations.facility import GenericObservationForm
from tom_common.exceptions import ImproperCredentialsException
from tom_observations.facility import GenericObservationFacility
from tom_targets.models import Target

try:
    GEM_SETTINGS = settings.FACILITIES['GEM']
except AttributeError:
    GEM_SETTINGS = {
        # 'portal_url': 'https://139.229.34.15:8443',
        'portal_url': 'https://gsodbtest.gemini.edu:8443',
        'api_key': '',
    }

PORTAL_URL = GEM_SETTINGS['portal_url']
TERMINAL_OBSERVING_STATES = ['TRIGGERED', 'ON_HOLD']
SITES = {
    'Cerro Pachon': {
        'sitecode': 'cpo',
        'latitude': -30.24075,
        'longitude': -70.736694,
        'elevation': 2722.
    },
    'Maunakea': {
        'sitecode': 'mko',
        'latitude': 19.8238,
        'longitude': -155.46905,
        'elevation': 4213.
    }
}


def make_request(*args, **kwargs):
    response = requests.request(*args, **kwargs)
    if 400 <= response.status_code < 500:
        raise ImproperCredentialsException('GEM')
    response.raise_for_status()
    return response


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


# def get_instruments():
#     response = make_request(
#         'GET',
#         PORTAL_URL + '/api/instruments/',
#         headers={'Authorization': 'Token {0}'.format(GEM_SETTINGS['api_key'])}
#     )
#     return response.json()
# 
# 
# def instrument_choices():
#     return [(k, k) for k in get_instruments()]
# 
# 
# def filter_choices():
#     return set([(f, f) for ins in get_instruments().values() for f in ins['filters']])


def proposal_choices():
    choices = ''
#     response = make_request(
#         'GET',
#         PORTAL_URL + '/api/profile/',
#         headers={'Authorization': 'Token {0}'.format(GEM_SETTINGS['api_key'])}
#     )
#     choices = []
#     for p in response.json()['proposals']:
#         if p['current']:
#             choices.append((p['id'], '{} ({})'.format(p['title'], p['id'])))
    return choices


class GEMObservationForm(GenericObservationForm):
    progid = forms.CharField()
    userkey = forms.CharField()
    email = forms.CharField()
    obsnum = forms.IntegerField(min_value=1)
    ready = forms.ChoiceField(
        choices=(('false', 'No'), ('true', 'Yes'))
    )
    brightness = forms.FloatField(required=False)
    brightness_system =forms.ChoiceField(required=False,
        choices=(('Vega', 'Vega'), ('AB', 'AB'), ('JY', 'Jy'))
    )
    brightness_band = forms.ChoiceField(required=False,
        choices=(('u', 'u'), ('U', 'U'), ('B', 'B'), ('g', 'g'), ('V', 'V'), ('UC', 'UC'), ('r', 'r'), ('R', 'R'),
                 ('i', 'i'), ('I', 'I'), ('z', 'z'), ('Y', 'Y'), ('J', 'J'), ('H', 'H'), ('K', 'K'), ('L', 'L'),
                 ('M', 'M'), ('N', 'N'), ('Q', 'Q'), ('AP', 'AP'))
    )
    posangle = forms.FloatField(min_value=0., max_value=360., required=False)
    # posangle = forms.FloatField(min_value=0., max_value=360.,help_text="Position angle in degrees [0-360]")
    pamode = forms.ChoiceField(required=False,
        choices=(('FLIP', 'Flip180'), ('FIXED', 'Fixed'), ('FIND', 'Find'), ('PARALLACTIC', 'Parallactic'))
    )
    group = forms.CharField(required=False)
    note = forms.CharField(required=False)

    # gstarg = forms.CharField(required=False)
    # gsra = forms.CharField(required=False)
    # gsdec = forms.CharField(required=False)
    # gsbrightness = forms.FloatField(required=False)
    # gsbrightness_system =forms.ChoiceField(required=False,
    #     choices=(('VEGA', 'Vega'), ('AB', 'AB'), ('JY', 'Jy'))
    # )
    # gsbrightness_band = forms.ChoiceField(required=False,
    #     choices=(('UP', 'u'), ('U', 'U'), ('B', 'B'), ('GP', 'g'), ('V', 'V'), ('UC', 'UC'), ('RP', 'r'), ('R', 'R'),
    #              ('IP', 'i'), ('I', 'I'), ('ZP', 'z'), ('Y', 'Y'), ('J', 'J'), ('H', 'H'), ('K', 'K'), ('L', 'L'),
    #              ('M', 'M'), ('N', 'N'), ('Q', 'Q'), ('AP', 'AP'))
    # )
    #
    # obsdate = forms.CharField(required=False,widget=forms.TextInput(attrs={'type': 'date'}))

    #     start = forms.CharField(widget=forms.TextInput(attrs={'type': 'date'}))
#     end = forms.CharField(widget=forms.TextInput(attrs={'type': 'date'}))
#     filter = forms.ChoiceField(choices=filter_choices)
#     instrument_name = forms.ChoiceField(choices=instrument_choices)
#     exposure_count = forms.IntegerField(min_value=1)
#     exposure_time = forms.FloatField(min_value=0.1)
#     max_airmass = forms.FloatField()
#     observation_type = forms.ChoiceField(
#         choices=(('NORMAL', 'Normal'), ('TARGET_OF_OPPORTUNITY', 'Rapid Response'))
#     )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.helper.layout = Layout(
            self.common_layout,
            Div(
                Div(
                    'progid', 'obsnum', 'brightness', 'group',
                    css_class='col'
                ),
                Div(
                    'email', 'posangle', 'brightness_band', 'note',
                    css_class='col'
                ),
                Div(
                    'userkey', 'pamode', 'brightness_system', 'ready',
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
        errors = GEMFacility.validate_observation(self.observation_payload)
        if errors:
            self.add_error(None, flatten_error_dict(self, errors))
        return not errors

#     def instrument_to_type(self, instrument_name):
#         if any(x in instrument_name for x in ['FLOYDS', 'NRES']):
#             return 'SPECTRUM'
#         else:
#             return 'EXPOSE'

    @property
    def observation_payload(self):
        target = Target.objects.get(pk=self.cleaned_data['target_id'])

        payload = {
            "prog": self.cleaned_data['progid'],
            "password": self.cleaned_data['userkey'],
            "email": self.cleaned_data['email'],
            "obsnum": self.cleaned_data['obsnum'],
            "target": target.name,
            "ra": target.ra,
            "dec": target.dec,
            "note": self.cleaned_data['note'],
            "posangle": str(self.cleaned_data['posangle']).strip(),
            "ready": self.cleaned_data['ready']
        }

        if str(self.cleaned_data['brightness']).strip() != '':
            smags = str(self.cleaned_data['brightness']).strip() + '/' + \
                self.cleaned_data['brightness_band'].strip() + '/' + \
                self.cleaned_data['brightness_system'].strip()
            payload["mags"] = smags

        if self.cleaned_data['group'].strip() != '':
            payload['group'] = self.cleaned_data['group'].strip()

        # # Guide star
        # if self.cleaned_data['gstarg'].strip() != '':
        #     payload['gstarget'] = self.cleaned_data['gstarg']
        #     payload['gsra'] = self.cleaned_data['gsra']
        #     payload['gsdec'] = self.cleaned_data['gsdec']
        #     sgsmag = str(self.cleaned_data['smag']).strip() + '/UC/Vega'
        #     payload['gsmags'] = sgsmag
        #     payload['gsprobe'] = self.cleaned_data['gsprobe']
        #
        # # timing window?
        # if self.cleaned_data['wDate'].strip() != '':
        #     payload['windowDate'] = self.cleaned_data['wDate'].strip()
        #     payload['windowTime'] = self.cleaned_data['wTime'].strip()
        #     payload['windowDuration'] = str(self.cleaned_data['wDur)']).strip()
        #
        # # elevation/airmass
        # s_eltype = self.cleaned_data['eltype'].strip()
        # if s_eltype == 'airmass' or s_eltype == 'hourAngle':
        #     payload['elevationType'] = s_eltype
        #     payload['elevationMin'] = str(self.cleaned_data['elmin']).strip()
        #     payload['elevationMax'] = str(self.cleaned_data['elmax']).strip()
            
        return payload

class GEMFacility(GenericObservationFacility):
    name = 'GEM'
    form = GEMObservationForm

    @classmethod
    def submit_observation(clz, observation_payload):
        response = make_request(
            'POST',
            PORTAL_URL + '/too',
            verify=False,
            params=observation_payload
            # headers=clz._portal_headers()
        )
        # Return just observation number
        obsid = response.text.split('-')
        return [obsid[-1]]

    @classmethod
    def validate_observation(clz, observation_payload):
        # response = make_request(
        #     'POST',
        #     PORTAL_URL + '/api/userrequests/validate/',
        #     json=observation_payload,
        #     headers=clz._portal_headers()
        # )
        # return response.json()['errors']
        return {}

    @classmethod
    def get_observation_url(clz, observation_id):
        # return PORTAL_URL + '/requests/' + observation_id
        return ''

    @classmethod
    def get_terminal_observing_states(clz):
        return TERMINAL_OBSERVING_STATES

    @classmethod
    def get_observing_sites(clz):
        return SITES

    @classmethod
    def get_observation_status(clz, observation_id):
        # response = make_request(
        #     'GET',
        #     PORTAL_URL + '/api/requests/{0}'.format(observation_id),
        #     headers=clz._portal_headers()
        # )
        # return response.json()['state']
        return ''

    @classmethod
    def _portal_headers(clz):
        # if GEM_SETTINGS.get('api_key'):
        #     return {'Authorization': 'Token {0}'.format(GEM_SETTINGS['api_key'])}
        # else:
        #     return {}
        return {}

    @classmethod
    def _archive_headers(clz):
        # if GEM_SETTINGS.get('api_key'):
        #     archive_token = cache.get('GEM_ARCHIVE_TOKEN')
        #     if not archive_token:
        #         response = make_request(
        #             'GET',
        #             PORTAL_URL + '/api/profile/',
        #             headers={'Authorization': 'Token {0}'.format(GEM_SETTINGS['api_key'])}
        #         )
        #         archive_token = response.json().get('tokens', {}).get('archive')
        #         if archive_token:
        #             cache.set('GEM_ARCHIVE_TOKEN', archive_token, 3600)
        #             return {'Authorization': 'Bearer {0}'.format(archive_token)}
        #
        #     else:
        #         return {'Authorization': 'Bearer {0}'.format(archive_token)}
        # else:
        #     return {}
        return {}

    @classmethod
    def data_products(clz, observation_record, product_id=None):
        products = []
        # for frame in clz._archive_frames(observation_record.observation_id, product_id):
        #     products.append({
        #         'id': frame['id'],
        #         'filename': frame['filename'],
        #         'created': frame['DATE_OBS'],
        #         'url': frame['url']
        #     })
        return products

    @classmethod
    def _archive_frames(clz, observation_id, product_id=None):
        # todo save this key somewhere
        frames = []
        # if product_id:
        #     response = make_request(
        #         'GET',
        #         'https://archive-api.GEM.global/frames/{0}/'.format(product_id),
        #         headers=clz._archive_headers()
        #     )
        #     frames = [response.json()]
        # else:
        #     response = make_request(
        #         'GET',
        #         'https://archive-api.GEM.global/frames/?REQNUM={0}'.format(observation_id),
        #         headers=clz._archive_headers()
        #     )
        #     frames = response.json()['results']

        return frames
