import requests
from django.conf import settings
from django.core.cache import cache

from tom_observations.facilities.lco import LCOFacility, LCOBaseObservationForm
from tom_observations.facilities.lco import LCOImagingObservationForm, LCOSpectroscopyObservationForm
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

# There is currently only one available grating, which is required for spectroscopy.
SPECTRAL_GRATING = 'SYZY_400'


def make_request(*args, **kwargs):
    response = requests.request(*args, **kwargs)
    if 400 <= response.status_code < 500:
        raise ImproperCredentialsException('SOAR: ' + str(response.content))
    response.raise_for_status()
    return response


class SOARBaseObservationForm(LCOBaseObservationForm):

    @staticmethod
    def _get_instruments():
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

    @staticmethod
    def instrument_to_type(instrument_type):
        if 'IMAGER' in instrument_type:
            return 'EXPOSE'
        else:
            return 'SPECTRUM'


class SOARImagingObservationForm(SOARBaseObservationForm, LCOImagingObservationForm):

    @staticmethod
    def instrument_choices():
        return sorted(
            [(k, v['name']) for k, v in SOARImagingObservationForm._get_instruments().items() if 'IMAGE' in v['type']],
            key=lambda inst: inst[1]
        )

    @staticmethod
    def filter_choices():
        return sorted(set([
            (f['code'], f['name']) for ins in SOARImagingObservationForm._get_instruments().values() for f in
            ins['optical_elements'].get('filters', [])
            ]), key=lambda filter_tuple: filter_tuple[1])


class SOARSpectroscopyObservationForm(SOARBaseObservationForm, LCOSpectroscopyObservationForm):

    @staticmethod
    def instrument_choices():
        return sorted(
            [(k, v['name'])
             for k, v in SOARSpectroscopyObservationForm._get_instruments().items()
             if 'SPECTRA' in v['type']],
            key=lambda inst: inst[1])

    @staticmethod
    def filter_choices():
        return set([
            (f['code'], f['name']) for ins in SOARSpectroscopyObservationForm._get_instruments().values() for f in
            ins['optical_elements'].get('slits', [])
            ])

    def _build_instrument_config(self):
        instrument_configs = super()._build_instrument_config()

        instrument_configs[0]['optical_elements'] = {
            'slit': self.cleaned_data['filter'],
            'grating': SPECTRAL_GRATING
        }
        instrument_configs[0]['rotator_mode'] = 'SKY'

        return instrument_configs


class SOARFacility(LCOFacility):
    """
    The ``SOARFacility`` is the interface to the SOAR Telescope. For information regarding SOAR observing and the
    available parameters, please see https://noirlab.edu/science/observing-noirlab/observing-ctio/observing-soar.

    Please note that SOAR is only available in AEON-mode. It also uses the LCO API key, so to use this module, the
    LCO dictionary in FACILITIES in `settings.py` will need to be completed.
    """

    name = 'SOAR'
    observation_forms = {
        'IMAGING': SOARImagingObservationForm,
        'SPECTRA': SOARSpectroscopyObservationForm
    }
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

    def get_form(self, observation_type):
        return self.observation_forms.get(observation_type, SOARBaseObservationForm)

    def get_facility_weather_urls(self):
        """
        `facility_weather_urls = {'code': 'XYZ', 'sites': [ site_dict, ... ]}`
        where
        `site_dict = {'code': 'XYZ', 'weather_url': 'http://path/to/weather'}`
        """
        facility_weather_urls = {
            'code': 'SOAR',
            'sites': [
                {
                    'code': site['sitecode'],
                    'weather_url': 'https://noirlab.edu/science/observing-noirlab/weather-webcams/'
                                   'cerro-pachon/environmental-conditions'
                }
                for site in self.SITES.values()]
            }

        return facility_weather_urls
