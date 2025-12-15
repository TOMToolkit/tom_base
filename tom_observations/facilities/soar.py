import requests

from django import forms
from crispy_forms.bootstrap import Tab, Alert
from crispy_forms.layout import Div
from django.forms.widgets import HiddenInput

from tom_observations.facilities.lco import LCOFacility, LCOSettings, SpectralInstrumentConfigLayout
from tom_observations.facilities.lco import LCOImagingObservationForm, LCOSpectroscopyObservationForm
from tom_observations.facilities.lco import SpectralConfigurationLayout
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


class SOARSimpleGoodmanSpectroscopyObservationForm(SOARSpectroscopyObservationForm):
    def __init__(self, *args, **kwargs):
        if 'facility_settings' not in kwargs:
            kwargs['facility_settings'] = SOARSettings("SOAR")
        super().__init__(*args, **kwargs)
        # Set default values for Arcs/Flats
        self.fields['c_2_configuration_type'].initial = "ARC"
        self.fields['c_2_ic_1_exposure_time'].initial = 0.5
        self.fields['c_2_target_override'].widget = HiddenInput()
        self.fields['c_3_configuration_type'].initial = "LAMP_FLAT"
        self.fields['c_3_ic_1_exposure_time'].initial = 0.5
        self.fields['c_3_target_override'].widget = HiddenInput()
        for j in range(2, 4):
            for i in range(self.facility_settings.get_setting('max_instrument_configs')):
                self.fields[f'c_{j}_ic_{i+1}_readout_mode'].widget = HiddenInput()
                self.fields[f'c_{j}_ic_{i+1}_exposure_time'].help_text = "Exposure time is hard-coded, " \
                                                                         "and the value is ignored for Flats/Arcs. " \
                                                                         "Any value will cause the calibration to be " \
                                                                         "scheduled."

    def form_name(self):
        if 'BLUE' in self.initial.get('observation_type', ''):
            return 'BlueCam'
        return 'RedCam'

    def get_instruments(self):
        instruments = super()._get_instruments()
        return {
            code: instrument for (code, instrument) in instruments.items() if ('SPECTRA' == instrument['type'] and
                                                                               'SOAR' in code and
                                                                               self.form_name() in instrument['name'])
        }

    def _build_instrument_configs(self, instrument_type, configuration_id):
        ics = super()._build_instrument_configs(instrument_type, configuration_id)
        # Overwrite the Lamp/Arc readout mode to be the same mode as the initial spectrum
        if configuration_id != 1:
            for j, ic in enumerate(ics):
                ic['mode'] = self._build_instrument_config(instrument_type, 1, j + 1)['mode']
        return ics

    def configuration_layout_class(self):
        return SOARSimpleConfigurationLayout


class SOARSimpleConfigurationLayout(SpectralConfigurationLayout):
    def _get_config_tabs(self, oe_groups, num_tabs):
        tabs = [Tab('Spectrum',
                    *self._get_config_layout(1, oe_groups),
                    css_id=f'{self.form_name}_config_{1}'
                    ),
                Tab('Arc',
                    *self._get_config_layout(2, oe_groups),
                    css_id=f'{self.form_name}_config_{2}'
                    ),
                Tab('Lamp Flat',
                    *self._get_config_layout(3, oe_groups),
                    css_id=f'{self.form_name}_config_{3}'
                    )
                ]

        return tuple(tabs)

    def _get_basic_config_layout(self, instance):
        return (
            Alert(
                content="""Make sure the instrument and readout match the current load-out for SOAR.
                                    """,
                css_class='alert-warning'
            ),
            Alert(
                content="""An Arc and a Lamp FLat will be automatically generated for this observation.
                                    """,
                css_class='alert-success'
            ),
            Div(
                Div(
                    f'c_{instance}_instrument_type',
                    css_class='col'
                ),
                Div(
                    f'c_{instance}_configuration_type',
                    css_class='col'
                ),
                css_class='form-row'
            ),
        )


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

    .. code-block:: python
        :caption: settings.py

        FACILITIES = {
            'SOAR': {
                'portal_url': 'https://observe.lco.global',
                'api_key': os.getenv('LCO_API_KEY'),
            },
        }

    """
    name = 'SOAR'
    observation_forms = {
        'IMAGING': SOARImagingObservationForm,
        'Goodman_BLUE_Spectra': SOARSimpleGoodmanSpectroscopyObservationForm,
        'Goodman_RED_Spectra': SOARSimpleGoodmanSpectroscopyObservationForm,
        'SPECTRA_Advanced': SOARSpectroscopyObservationForm,
    }

    def __init__(self, facility_settings=SOARSettings("SOAR")):
        super().__init__(facility_settings=facility_settings)

    def get_form(self, observation_type):
        return self.observation_forms.get(observation_type, SOARImagingObservationForm)
