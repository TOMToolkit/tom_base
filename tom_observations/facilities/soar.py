import requests

from django import forms
from crispy_forms.layout import Div

from tom_observations.facilities.lco import LCOFacility, LCOSettings, SpectralInstrumentConfigLayout
from tom_observations.facilities.lco import LCOImagingObservationForm, LCOSpectroscopyObservationForm
from tom_common.exceptions import ImproperCredentialsException


class SOARSettings(LCOSettings):

    instrument_type_help = """
            <a href="https://noirlab.edu/science/programs/ctio/telescopes/soar-telescope/instruments" target="_blank">
                More information about SOAR instruments.
            </a>
        """

    exposure_time_help = """
        """

    rotator_mode_help = """
        """

    rotator_angle_help = """
        """

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

    def __init__(self, facility_name='SOAR'):
        super().__init__(facility_name=facility_name)


def make_request(*args, **kwargs):
    response = requests.request(*args, **kwargs)
    if 400 <= response.status_code < 500:
        raise ImproperCredentialsException('SOAR: ' + str(response.content))
    response.raise_for_status()
    return response


class SOARImagingObservationForm(LCOImagingObservationForm):
    def __init__(self, *args, **kwargs):
        # Set the facility settings to the SOAR settings
        if 'facility_settings' not in kwargs:
            kwargs['facility_settings'] = SOARSettings("SOAR")
        super().__init__(*args, **kwargs)

    def get_instruments(self):
        instruments = super()._get_instruments()
        return {
            code: instrument for (code, instrument) in instruments.items() if (
                'IMAGE' == instrument['type'] and 'SOAR' in code)
        }

    def configuration_type_choices(self):
        return [('EXPOSE', 'Exposure')]


class SOARSpectroscopyObservationForm(LCOSpectroscopyObservationForm):
    def __init__(self, *args, **kwargs):
        # Set the facility settings to the SOAR settings
        if 'facility_settings' not in kwargs:
            kwargs['facility_settings'] = SOARSettings("SOAR")
        super().__init__(*args, **kwargs)
        # Add readout mode field for each instrument configuration since LCO doesn't have this field for spectroscopy
        for j in range(self.facility_settings.get_setting('max_configurations')):
            for i in range(self.facility_settings.get_setting('max_instrument_configs')):
                self.fields[f'c_{j + 1}_ic_{i + 1}_readout_mode'] = forms.ChoiceField(
                    choices=self.mode_choices('readout'), required=False, label='Readout Mode')

    def get_instruments(self):
        instruments = super()._get_instruments()
        return {
            code: instrument for (code, instrument) in instruments.items() if (
                'SPECTRA' == instrument['type'] and 'SOAR' in code)
        }

    def configuration_type_choices(self):
        return [('SPECTRUM', 'Spectrum'), ('ARC', 'Arc'), ('LAMP_FLAT', 'Lamp Flat')]

    def instrument_config_layout_class(self):
        return SoarSpectralInstrumentConfigLayout


class SoarSpectralInstrumentConfigLayout(SpectralInstrumentConfigLayout):
    def _get_ic_layout(self, config_instance, instance, oe_groups):
        return (
            Div(
                Div(
                    f'c_{config_instance}_ic_{instance}_readout_mode',
                    css_class='col'
                ),
                css_class='form-row'
            ),
            Div(
                Div(
                    f'c_{config_instance}_ic_{instance}_exposure_time',
                    css_class='col'
                ),
                Div(
                    f'c_{config_instance}_ic_{instance}_exposure_count',
                    css_class='col'
                ),
                css_class='form-row'
            ),
            Div(
                Div(
                    f'c_{config_instance}_ic_{instance}_rotator_mode',
                    css_class='col'
                ),
                Div(
                    f'c_{config_instance}_ic_{instance}_rotator_angle',
                    css_class='col'
                ),
                css_class='form-row'
            ),
            *self._get_oe_groups_layout(config_instance, instance, oe_groups)
        )


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

    def __init__(self, facility_settings=SOARSettings("SOAR")):
        super().__init__(facility_settings=facility_settings)

    def get_form(self, observation_type):
        return self.observation_forms.get(observation_type, SOARImagingObservationForm)
