import requests
from django.conf import settings
from django.core.cache import cache

from tom_observations.facilities.lco import LCOFacility, LCOBaseForm
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


class SOARImagingObservationForm(LCOImagingObservationForm):

    def get_instruments(self):
        instruments = LCOBaseForm._get_instruments()
        return {
            code: instrument for (code, instrument) in instruments.items() if (
                'IMAGE' == instrument['type'] and 'SOAR' in code)
        }

    def configuration_type_choices(self):
        return [('EXPOSE', 'Exposure')]


class SOARSpectroscopyObservationForm(LCOSpectroscopyObservationForm):
    def get_instruments(self):
        instruments = LCOBaseForm._get_instruments()
        return {
            code: instrument for (code, instrument) in instruments.items() if (
                'SPECTRA' == instrument['type'] and 'SOAR' in code)
        }

    def configuration_type_choices(self):
        return [('SPECTRUM', 'Spectrum'), ('ARC', 'Arc'), ('LAMP_FLAT', 'Lamp Flat')]


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
        return self.observation_forms.get(observation_type, SOARImagingObservationForm)

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
