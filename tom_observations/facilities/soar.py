import requests
from django.conf import settings
from django.core.cache import cache

from tom_observations.facilities.lco import LCOObservationForm, LCOFacility
from tom_common.exceptions import ImproperCredentialsException


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


# The SITES dictionary is used to calculate visibility intervals in the
# planning tool. All entries should contain latitude, longitude, elevation
# and a code.
SITES = {
    'Cerro Pachón': {
        'sitecode': 'sor',
        'latitude': -30.237892,
        'longitude': -70.733642,
        'elevation': 2000
    }
}

# There is currently only one available grating, which is required for spectroscopy.
SPECTRAL_GRATING = 'SYZY_400'


def make_request(*args, **kwargs):
    response = requests.request(*args, **kwargs)
    if 400 <= response.status_code < 500:
        raise ImproperCredentialsException('SOAR: ' + str(response.content))
    response.raise_for_status()
    return response


class SOARObservationForm(LCOObservationForm):

    def _get_instruments(self):
        cached_instruments = cache.get('soar_instruments')

        if not cached_instruments:
            response = make_request(
                'GET',
                PORTAL_URL + '/api/instruments/',
                headers={'Authorization': 'Token {0}'.format(LCO_SETTINGS['api_key'])}
            )

            cached_instruments = {k: v for k, v in response.json().items() if 'SOAR' in k}
            cache.set('soar_instruments', cached_instruments)

        return cached_instruments

    def instrument_to_type(self, instrument_type):
        if 'IMAGER' in instrument_type:
            return 'EXPOSE'
        else:
            return 'SPECTRUM'

    def _build_instrument_config(self):
        instrument_config = {
                'exposure_count': self.cleaned_data['exposure_count'],
                'exposure_time': self.cleaned_data['exposure_time'],
                'rotator_mode': 'SKY',
                'extra_params': {
                    'rotator_angle': 0  # TODO: This should be a part of the eventual distinct spectroscopy form
                }
        }

        if self.instrument_to_type(self.cleaned_data['instrument_type']) == 'EXPOSE':
            instrument_config['optical_elements'] = {
                'filter': self.cleaned_data['filter']
            }
        else:
            instrument_config['optical_elements'] = {
                'slit': self.cleaned_data['filter'],
                'grating': SPECTRAL_GRATING
            }

        return instrument_config


class SOARFacility(LCOFacility):
    name = 'SOAR'
    form = SOARObservationForm
