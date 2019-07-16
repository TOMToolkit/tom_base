import requests
from django.conf import settings
from django import forms
from dateutil.parser import parse
from crispy_forms.layout import Layout, Div
from django.core.cache import cache
from astropy import units as u

from tom_observations.facility import GenericObservationForm
from tom_common.exceptions import ImproperCredentialsException
from tom_observations.facility import GenericObservationFacility, get_service_class
from tom_targets.models import Target

# Determine settings for this module.
try:
    LCO_SETTINGS = settings.FACILITIES['LCO']
except (AttributeError, KeyError):
    LCO_SETTINGS = {
        'portal_url': 'https://observe.lco.global',
        'api_key': '',
    }

# Module specific settings.
PORTAL_URL = LCO_SETTINGS['portal_url']
TERMINAL_OBSERVING_STATES = ['COMPLETED', 'CANCELED', 'WINDOW_EXPIRED']

# Units of flux and wavelength for converting to Specutils Spectrum1D objects
FLUX_CONSTANT = (1e-15 * u.erg) / (u.cm ** 2 * u.second * u.angstrom)
WAVELENGTH_UNITS = u.angstrom

# The SITES dictionary is used to calculate visibility intervals in the
# planning tool. All entries should contain latitude, longitude, elevation
# and a code.
SITES = {
    'Siding Spring': {
        'sitecode': 'coj',
        'latitude': -31.272,
        'longitude': 149.07,
        'elevation': 1116
    },
    'Sutherland': {
        'sitecode': 'cpt',
        'latitude': -32.38,
        'longitude': 20.81,
        'elevation': 1804
    },
    'Teide': {
        'sitecode': 'tfn',
        'latitude': 20.3,
        'longitude': -16.511,
        'elevation': 2390
    },
    'Cerro Tololo': {
        'sitecode': 'lsc',
        'latitude': -30.167,
        'longitude': -70.804,
        'elevation': 2198
    },
    'McDonald': {
        'sitecode': 'elp',
        'latitude': 30.679,
        'longitude': -104.015,
        'elevation': 2027
    },
    'Haleakala': {
        'sitecode': 'ogg',
        'latitude': 20.706,
        'longitude': -156.258,
        'elevation': 3065
    }
}

# Functions needed specifically for LCO


def make_request(*args, **kwargs):
    response = requests.request(*args, **kwargs)
    if 400 <= response.status_code < 500:
        raise ImproperCredentialsException('LCO: ' + str(response.content))
    response.raise_for_status()
    return response


def _flatten_error_dict(form, error_dict):
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
                    non_field_errors.append(_flatten_error_dict(form, i))
        elif type(v) == str:
            if k in form.fields:
                form.add_error(k, v)
            else:
                non_field_errors.append('{}: {}'.format(k, v))
        elif type(v) == dict:
            non_field_errors.append(_flatten_error_dict(form, v))

    return non_field_errors


def _get_instruments():
    cached_instruments = cache.get('lco_instruments')

    if not cached_instruments:
        response = make_request(
            'GET',
            PORTAL_URL + '/api/instruments/',
            headers={'Authorization': 'Token {0}'.format(LCO_SETTINGS['api_key'])}
        )
        cached_instruments = response.json()
        cache.set('lco_instruments', cached_instruments)

    return cached_instruments


def instrument_choices():
    return [(k, k) for k in _get_instruments()]


def filter_choices():
    return set([
            (f['code'], f['name']) for ins in _get_instruments().values() for f in
            ins['optical_elements'].get('filters', []) + ins['optical_elements'].get('slits', [])
            ])


def proposal_choices():
    response = make_request(
        'GET',
        PORTAL_URL + '/api/profile/',
        headers={'Authorization': 'Token {0}'.format(LCO_SETTINGS['api_key'])}
    )
    choices = []
    for p in response.json()['proposals']:
        if p['current']:
            choices.append((p['id'], '{} ({})'.format(p['title'], p['id'])))
    return choices


class LCOObservationForm(GenericObservationForm):
    name = forms.CharField()
    proposal = forms.ChoiceField(choices=proposal_choices)
    ipp_value = forms.FloatField()
    start = forms.CharField(widget=forms.TextInput(attrs={'type': 'date'}))
    end = forms.CharField(widget=forms.TextInput(attrs={'type': 'date'}))
    filter = forms.ChoiceField(choices=filter_choices)
    instrument_type = forms.ChoiceField(choices=instrument_choices)
    exposure_count = forms.IntegerField(min_value=1)
    exposure_time = forms.FloatField(min_value=0.1)
    max_airmass = forms.FloatField()
    observation_type = forms.ChoiceField(
        choices=(('NORMAL', 'Normal'), ('TARGET_OF_OPPORTUNITY', 'Rapid Response'))
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.helper.layout = Layout(
            self.common_layout,
            self.layout(),
            self.extra_layout()
        )

    def layout(self):
        return Div(
            Div(
                'name', 'proposal', 'ipp_value', 'observation_type', 'start', 'end',
                css_class='col'
            ),
            Div(
                'filter', 'instrument_type', 'exposure_count', 'exposure_time', 'max_airmass',
                css_class='col'
            ),
            css_class='form-row'
        )

    def extra_layout(self):
        # If you just want to add some fields to the end of the form, add them here.
        return Div()

    def clean_start(self):
        start = self.cleaned_data['start']
        return parse(start).isoformat()

    def clean_end(self):
        end = self.cleaned_data['end']
        return parse(end).isoformat()

    def is_valid(self):
        super().is_valid()
        # TODO this is a bit leaky and should be done without the need of get_service_class
        obs_module = get_service_class(self.cleaned_data['facility'])
        errors = obs_module().validate_observation(self.observation_payload())
        if errors:
            self.add_error(None, _flatten_error_dict(self, errors))
        return not errors

    def instrument_to_type(self, instrument_type):
        if any(x in instrument_type for x in ['FLOYDS', 'NRES']):
            return 'SPECTRUM'
        else:
            return 'EXPOSE'

    def observation_payload(self):
        target = Target.objects.get(pk=self.cleaned_data['target_id'])
        target_fields = {
            "name": target.name,
        }
        if target.type == Target.SIDEREAL:
            target_fields['type'] = 'ICRS'
            target_fields['ra'] = target.ra
            target_fields['dec'] = target.dec
            target_fields['proper_motion_ra'] = target.pm_ra
            target_fields['proper_motion_dec'] = target.pm_dec
            target_fields['epoch'] = target.epoch
        elif target.type == Target.NON_SIDEREAL:
            target_fields['type'] = 'ORBITAL_ELEMENTS'
            target_fields['scheme'] = target.scheme
            target_fields['orbinc'] = target.inclination
            target_fields['longascnode'] = target.lng_asc_node
            target_fields['argofperih'] = target.arg_of_perihelion
            target_fields['eccentricity'] = target.eccentricity
            target_fields['meandist'] = target.semimajor_axis
            target_fields['meananom'] = target.mean_anomaly
            target_fields['perihdist'] = target.distance
            target_fields['dailymot'] = target.mean_daily_motion
            target_fields['epochofel'] = target.epoch
            target_fields['epochofperih'] = target.epoch_of_perihelion

        if self.instrument_to_type(self.cleaned_data['instrument_type']) == 'EXPOSE':
            optical_elements = {
                'filter': self.cleaned_data['filter'],
            }
        else:
            optical_elements = {
                "slit": self.cleaned_data['filter'],
            }

        return {
            "name": self.cleaned_data['name'],
            "proposal": self.cleaned_data['proposal'],
            "ipp_value": self.cleaned_data['ipp_value'],
            "operator": "SINGLE",
            "observation_type": self.cleaned_data['observation_type'],
            "requests": [
                {
                    "configurations": [
                        {
                            "type": self.instrument_to_type(self.cleaned_data['instrument_type']),
                            "instrument_type": self.cleaned_data['instrument_type'],
                            "target": target_fields,
                            "instrument_configs": [
                                {
                                    "exposure_count": self.cleaned_data['exposure_count'],
                                    "exposure_time": self.cleaned_data['exposure_time'],
                                    "optical_elements": optical_elements
                                }
                            ],
                            "acquisition_config": {

                            },
                            "guiding_config": {

                            },
                            "constraints": {
                               "max_airmass": self.cleaned_data['max_airmass'],
                            }
                        }
                    ],
                    "windows": [
                        {
                            "start": self.cleaned_data['start'],
                            "end": self.cleaned_data['end']
                        }
                    ],
                    "location": {
                        "telescope_class": self.cleaned_data['instrument_type'][:3].lower()
                    }
                }
            ]
        }


class LCOFacility(GenericObservationFacility):
    name = 'LCO'
    form = LCOObservationForm

    def submit_observation(self, observation_payload):
        response = make_request(
            'POST',
            PORTAL_URL + '/api/requestgroups/',
            json=observation_payload,
            headers=self._portal_headers()
        )
        return [r['id'] for r in response.json()['requests']]

    def validate_observation(self, observation_payload):
        response = make_request(
            'POST',
            PORTAL_URL + '/api/requestgroups/validate/',
            json=observation_payload,
            headers=self._portal_headers()
        )
        return response.json()['errors']

    def get_observation_url(self, observation_id):
        return PORTAL_URL + '/requests/' + observation_id

    def get_flux_constant(self):
        return FLUX_CONSTANT

    def get_wavelength_units(self):
        return WAVELENGTH_UNITS

    def get_terminal_observing_states(self):
        return TERMINAL_OBSERVING_STATES

    def get_observing_sites(self):
        return SITES

    def get_observation_status(self, observation_id):
        response = make_request(
            'GET',
            PORTAL_URL + '/api/requests/{0}'.format(observation_id),
            headers=self._portal_headers()
        )
        state = response.json()['state']

        response = make_request(
            'GET',
            PORTAL_URL + '/api/requests/{0}/observations/'.format(observation_id),
            headers=self._portal_headers()
        )
        blocks = response.json()
        current_block = None
        for block in blocks:
            if block['state'] == 'COMPLETED':
                current_block = block
                break
            elif block['state'] == 'PENDING':
                current_block = block
        if current_block:
            scheduled_start = current_block['start']
            scheduled_end = current_block['end']
        else:
            scheduled_start, scheduled_end = None, None

        return {'state': state, 'scheduled_start': scheduled_start, 'scheduled_end': scheduled_end}

    def data_products(self, observation_id, product_id=None):
        products = []
        for frame in self._archive_frames(observation_id, product_id):
            products.append({
                'id': frame['id'],
                'filename': frame['filename'],
                'created': parse(frame['DATE_OBS']),
                'url': frame['url']
            })
        return products

    # The following methods are used internally by this module
    # and should not be called directly from outside code.

    def _portal_headers(self):
        if LCO_SETTINGS.get('api_key'):
            return {'Authorization': 'Token {0}'.format(LCO_SETTINGS['api_key'])}
        else:
            return {}

    def _archive_headers(self):
        if LCO_SETTINGS.get('api_key'):
            archive_token = cache.get('LCO_ARCHIVE_TOKEN')
            if not archive_token:
                response = make_request(
                    'GET',
                    PORTAL_URL + '/api/profile/',
                    headers={'Authorization': 'Token {0}'.format(LCO_SETTINGS['api_key'])}
                )
                archive_token = response.json().get('tokens', {}).get('archive')
                if archive_token:
                    cache.set('LCO_ARCHIVE_TOKEN', archive_token, 3600)
                    return {'Authorization': 'Bearer {0}'.format(archive_token)}

            else:
                return {'Authorization': 'Bearer {0}'.format(archive_token)}
        else:
            return {}

    def _archive_frames(self, observation_id, product_id=None):
        # todo save this key somewhere
        frames = []
        if product_id:
            response = make_request(
                'GET',
                'https://archive-api.lco.global/frames/{0}/'.format(product_id),
                headers=self._archive_headers()
            )
            frames = [response.json()]
        else:
            response = make_request(
                'GET',
                'https://archive-api.lco.global/frames/?REQNUM={0}'.format(observation_id),
                headers=self._archive_headers()
            )
            frames = response.json()['results']

        return frames
