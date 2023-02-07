import requests

from tom_observations.facilities.lco import LCOFacility, LCOSettings
from tom_observations.facilities.lco import LCOImagingObservationForm, LCOSpectroscopyObservationForm
from tom_common.exceptions import ImproperCredentialsException


class SOARSettings(LCOSettings):
    def get_sites(self):
        return {
            'Cerro Pachón': {
                'sitecode': 'sor',
                'latitude': -30.237892,
                'longitude': -70.733642,
                'elevation': 2000
            }
        }

    def get_weather_urls(self):
        return {
            'code': 'SOAR',
            'sites': [
                {
                    'code': site['sitecode'],
                    'weather_url': 'https://noirlab.edu/science/observing-noirlab/weather-webcams/'
                                   'cerro-pachon/environmental-conditions'
                }
                for site in self.get_sites().values()]
        }


def make_request(*args, **kwargs):
    response = requests.request(*args, **kwargs)
    if 400 <= response.status_code < 500:
        raise ImproperCredentialsException('SOAR: ' + str(response.content))
    response.raise_for_status()
    return response


class SOARImagingObservationForm(LCOImagingObservationForm):

    def get_instruments(self):
        instruments = super()._get_instruments()
        return {
            code: instrument for (code, instrument) in instruments.items() if (
                'IMAGE' == instrument['type'] and 'SOAR' in code)
        }

    def configuration_type_choices(self):
        return [('EXPOSE', 'Exposure')]


class SOARSpectroscopyObservationForm(LCOSpectroscopyObservationForm):
    def get_instruments(self):
        instruments = super()._get_instruments()
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

    def __init__(self, facility_settings=SOARSettings('LCO')):
        super().__init__(facility_settings=facility_settings)

    def get_form(self, observation_type):
        return self.observation_forms.get(observation_type, SOARImagingObservationForm)
