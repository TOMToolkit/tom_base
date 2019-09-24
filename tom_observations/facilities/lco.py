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
from tom_targets.models import (
    Target, REQUIRED_NON_SIDEREAL_FIELDS,
    REQUIRED_NON_SIDEREAL_FIELDS_PER_SCHEME
)

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

# FITS header keywords used for data processing
FITS_FACILITY_KEYWORD = 'ORIGIN'
FITS_FACILITY_KEYWORD_VALUE = 'LCOGT'
FITS_FACILITY_DATE_OBS_KEYWORD = 'DATE-OBS'

# Functions needed specifically for LCO


def make_request(*args, **kwargs):
    response = requests.request(*args, **kwargs)
    if 400 <= response.status_code < 500:
        raise ImproperCredentialsException('LCO: ' + str(response.content))
    response.raise_for_status()
    return response


class LCOBaseObservationForm(GenericObservationForm):
    name = forms.CharField()
    ipp_value = forms.FloatField()
    start = forms.CharField(widget=forms.TextInput(attrs={'type': 'date'}))
    end = forms.CharField(widget=forms.TextInput(attrs={'type': 'date'}))
    exposure_count = forms.IntegerField(min_value=1)
    exposure_time = forms.FloatField(min_value=0.1)
    max_airmass = forms.FloatField()
    observation_mode = forms.ChoiceField(
        choices=(('NORMAL', 'Normal'), ('TARGET_OF_OPPORTUNITY', 'Rapid Response'))
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['proposal'] = forms.ChoiceField(choices=self.proposal_choices())
        self.fields['filter'] = forms.ChoiceField(choices=self.filter_choices())
        self.fields['instrument_type'] = forms.ChoiceField(choices=self.instrument_choices())
        self.helper.layout = Layout(
            self.common_layout,
            self.layout(),
            self.extra_layout()
        )

    def layout(self):
        return Div(
            Div(
                'name', 'proposal', 'ipp_value', 'observation_mode', 'start', 'end',
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

    def _get_instruments(self):
        cached_instruments = cache.get('lco_instruments')

        if not cached_instruments:
            response = make_request(
                'GET',
                PORTAL_URL + '/api/instruments/',
                headers={'Authorization': 'Token {0}'.format(LCO_SETTINGS['api_key'])}
            )
            cached_instruments = {k: v for k, v in response.json().items() if 'SOAR' not in k}
            cache.set('lco_instruments', cached_instruments)

        return cached_instruments

    def instrument_choices(self):
        return [(k, v['name']) for k, v in self._get_instruments().items()]

    def filter_choices(self):
        return set([
            (f['code'], f['name']) for ins in self._get_instruments().values() for f in
            ins['optical_elements'].get('filters', []) + ins['optical_elements'].get('slits', [])
            ])

    def proposal_choices(self):
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
            self.add_error(None, self._flatten_error_dict(errors))
        return not errors

    def _flatten_error_dict(self, error_dict):
        non_field_errors = []
        for k, v in error_dict.items():
            if type(v) == list:
                for i in v:
                    if type(i) == str:
                        if k in self.fields:
                            self.add_error(k, i)
                        else:
                            non_field_errors.append('{}: {}'.format(k, i))
                    if type(i) == dict:
                        non_field_errors.append(self._flatten_error_dict(i))
            elif type(v) == str:
                if k in self.fields:
                    self.add_error(k, v)
                else:
                    non_field_errors.append('{}: {}'.format(k, v))
            elif type(v) == dict:
                non_field_errors.append(self._flatten_error_dict(v))

        return non_field_errors

    def instrument_to_type(self, instrument_type):
        if 'FLOYDS' in instrument_type:
            return 'SPECTRUM'
        elif 'NRES' in instrument_type:
            return 'NRES_SPECTRUM'
        else:
            return 'EXPOSE'

    def _build_target_fields(self):
        target = Target.objects.get(pk=self.cleaned_data['target_id'])
        target_fields = {
            'name': target.name,
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
            # Mapping from TOM field names to LCO API field names, for fields
            # where there are differences
            field_mapping = {
                'inclination': 'orbinc',
                'lng_asc_node': 'longascnode',
                'arg_of_perihelion': 'argofperih',
                'semimajor_axis': 'meandist',
                'mean_anomaly': 'meananom',
                'mean_daily_motion': 'dailymot',
                'epoch': 'epochofel',
                'epoch_of_perihelion': 'epochofperih',
            }
            # The fields to include in the payload depend on the scheme. Add
            # only those that are required
            fields = (REQUIRED_NON_SIDEREAL_FIELDS
                      + REQUIRED_NON_SIDEREAL_FIELDS_PER_SCHEME[target.scheme])
            for field in fields:
                lco_field = field_mapping.get(field, field)
                target_fields[lco_field] = getattr(target, field)

        return target_fields

    def _build_instrument_config(self):
        instrument_config = {
            'exposure_count': self.cleaned_data['exposure_count'],
            'exposure_time': self.cleaned_data['exposure_time'],
            'optical_elements': {
                'filter': self.cleaned_data['filter']
            }
        }

        return instrument_config

    def _build_configuration(self):
        return {
            'type': self.instrument_to_type(self.cleaned_data['instrument_type']),
            'instrument_type': self.cleaned_data['instrument_type'],
            'target': self._build_target_fields(),
            'instrument_configs': [self._build_instrument_config()],
            'acquisition_config': {

            },
            'guiding_config': {

            },
            'constraints': {
                'max_airmass': self.cleaned_data['max_airmass']
            }
        }

    def observation_payload(self):
        return {
            "name": self.cleaned_data['name'],
            "proposal": self.cleaned_data['proposal'],
            "ipp_value": self.cleaned_data['ipp_value'],
            "operator": "SINGLE",
            "observation_type": self.cleaned_data['observation_mode'],
            "requests": [
                {
                    "configurations": [self._build_configuration()],
                    "windows": [
                        {
                            "start": self.cleaned_data['start'],
                            "end": self.cleaned_data['end']
                        }
                    ],
                    "location": {
                        "telescope_class": self._get_instruments()[self.cleaned_data['instrument_type']]['class']
                    }
                }
            ]
        }


class LCOImagingObservationForm(LCOBaseObservationForm):
    def instrument_choices(self):
        return [(k, v['name']) for k, v in self._get_instruments().items() if 'IMAGE' in v['type']]

    def filter_choices(self):
        return set([
            (f['code'], f['name']) for ins in self._get_instruments().values() for f in
            ins['optical_elements'].get('filters', [])
            ])


class LCOSpectroscopyObservationForm(LCOBaseObservationForm):
    rotator_angle = forms.FloatField(min_value=0.0, initial=0.0)

    def layout(self):
        return Div(
            Div(
                'name', 'proposal', 'ipp_value', 'observation_mode', 'start', 'end',
                css_class='col'
            ),
            Div(
                'filter', 'instrument_type', 'exposure_count', 'exposure_time', 'max_airmass', 'rotator_angle',
                css_class='col'
            ),
            css_class='form-row'
        )

    def instrument_choices(self):
        return [(k, v['name']) for k, v in self._get_instruments().items() if 'SPECTRA' in v['type']]

    # NRES does not take a slit, and therefore needs an option of None
    def filter_choices(self):
        return set([
            (f['code'], f['name']) for ins in self._get_instruments().values() for f in
            ins['optical_elements'].get('slits', [])
            ] + [('None', 'None')])

    def _build_instrument_config(self):
        instrument_config = super()._build_instrument_config()
        if self.cleaned_data['filter'] != 'None':
            instrument_config['optical_elements'] = {
                'slit': self.cleaned_data['filter']
            }
        else:
            instrument_config.pop('optical_elements')
        instrument_config['rotator_mode'] = 'VFLOAT'  # TODO: Should be a distinct field, SKY & VFLOAT are both valid
        instrument_config['extra_params'] = {
            'rotator_angle': self.cleaned_data['rotator_angle']
        }

        return instrument_config


class LCOFacility(GenericObservationFacility):
    name = 'LCO'
    observation_types = [('IMAGING', 'Imaging'), ('SPECTRA', 'Spectroscopy')]
    # The SITES dictionary is used to calculate visibility intervals in the
    # planning tool. All entries should contain latitude, longitude, elevation
    # and a code.
    # TODO: Flip sitecode and site name
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

    def get_form(self, observation_type):
        if observation_type == 'IMAGING':
            return LCOImagingObservationForm
        elif observation_type == 'SPECTRA':
            return LCOSpectroscopyObservationForm
        else:
            return LCOBaseObservationForm

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

    def get_date_obs_from_fits_header(self, header):
        return header.get(FITS_FACILITY_DATE_OBS_KEYWORD, None)

    def is_fits_facility(self, header):
        """
        Returns True if the 'ORIGIN' keyword is in the given FITS header and contains the value 'LCOGT', False
        otherwise.

        :param header: FITS header object
        :type header: dictionary-like

        :returns: True if header matches LCOGT, False otherwise
        :rtype: boolean
        """
        return FITS_FACILITY_KEYWORD_VALUE == header.get(FITS_FACILITY_KEYWORD, None)

    def get_terminal_observing_states(self):
        return TERMINAL_OBSERVING_STATES

    def get_observing_sites(self):
        return self.SITES

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
            url = 'https://archive-api.lco.global/frames/?REQNUM={0}&limit=1000'.format(observation_id)
            while url:
                response = make_request(
                    'GET',
                    url,
                    headers=self._archive_headers()
                )
                frames.extend(response.json()['results'])
                url = response.json()['next']
        return frames
