import requests

from django import forms
from crispy_forms.layout import Div, HTML

from tom_observations.facilities.ocs import (OCSInstrumentConfigLayout, OCSConfigurationLayout,
                                             OCSFullObservationForm, OCSAdvancedExpansionsLayout)
from tom_observations.facilities.lco import LCOFacility, LCOSettings
from tom_common.exceptions import ImproperCredentialsException


class BLANCOSettings(LCOSettings):

    instrument_type_help = '<a href="https://noirlab.edu/science/programs/ctio/telescopes/victor-blanco-4m-telescope/' \
                           'Instruments-Available-Blanco-Telescope" target="_blank">' \
                           'More information about BLANCO instruments.' \
                           '</a>'

    exposure_time_help = """
        """

    rotator_mode_help = """
        """

    rotator_angle_help = """
        """

    def get_sites(self):
        return {
            'Cerro Tololo': {
                'sitecode': 'bco',
                'latitude': -30.16541667,
                'longitude': -70.81463889,
                'elevation': 2000
            }
        }

    def get_weather_urls(self):
        return {
            'code': 'BLANCO',
            'sites': [
                {
                    'code': site['sitecode'],
                    'weather_url': 'https://noirlab.edu/science/observing-noirlab/weather-webcams/'
                                   'cerro-tololo/environmental-conditions'
                }
                for site in self.get_sites().values()]
        }

    def __init__(self, facility_name='BLANCO'):
        super().__init__(facility_name=facility_name)


def make_request(*args, **kwargs):
    response = requests.request(*args, **kwargs)
    if 400 <= response.status_code < 500:
        raise ImproperCredentialsException('BLANCO: ' + str(response.content))
    response.raise_for_status()
    return response


class BLANCOAdvancedExpansionLayout(OCSAdvancedExpansionsLayout):
    def _get_dithering_tab(self):
        return (
                    Div(
                        HTML('''<br/><p>Dithering settings are a part of the BLANCO configuration above</p>'''),
                    )
                )


class BLANCOConfigurationLayout(OCSConfigurationLayout):
    def get_initial_accordion_items(self, instance):
        return (
            Div(
                Div(
                    f'c_{instance}_dither_value',
                    css_class='col'
                ),
                Div(
                    f'c_{instance}_dither_sequence',
                    css_class='col'
                ),
                css_class='form-row'
            ),
            Div(
                Div(
                    f'c_{instance}_detector_centering',
                    css_class='col'
                ),
                Div(
                    f'c_{instance}_dither_sequence_random_offset',
                    css_class='col'
                ),
                css_class='form-row'
            ),
        )


class BLANCOInstrumentConfigLayout(OCSInstrumentConfigLayout):
    def get_final_ic_items(self, config_instance, instance):
        return (
            Div(
                Div(
                    f'c_{config_instance}_ic_{instance}_coadds',
                    css_class='col'
                ),
                Div(
                    f'c_{config_instance}_ic_{instance}_sequence_repeats',
                    css_class='col'
                ),
                css_class='form-row'
            )
        )


class BLANCOImagingObservationForm(OCSFullObservationForm):
    """
    The BLANCOImagingObservationForm allows selection of blanco specific instrument parameters
    """
    DETECTOR_CENTERING_CHOICES = [('none', 'none'), ('det_1', 'det_1'), ('det_2', 'det_2'),
                                  ('det_3', 'det_3'), ('det_4', 'det_4')]
    DITHER_SEQUENCE_CHOICES = [('2x2', '2x2'), ('3x3', '3x3'), ('4x4', '4x4'), ('5-point', '5-point')]

    def __init__(self, *args, **kwargs):
        if 'facility_settings' not in kwargs:
            kwargs['facility_settings'] = BLANCOSettings("BLANCO")
        super().__init__(*args, **kwargs)
        # Need to add the blanco specific fields to this form
        for j in range(self.facility_settings.get_setting('max_configurations')):
            self.fields[f'c_{j+1}_dither_value'] = forms.IntegerField(
                    min_value=0, max_value=1600, initial=80, label='Dither Value',
                    help_text="The amount in arc seconds between dither points",
                    widget=forms.TextInput(attrs={'placeholder': 'Arc Seconds'}), required=True)
            self.fields[f'c_{j+1}_dither_sequence'] = forms.ChoiceField(
                choices=self.DITHER_SEQUENCE_CHOICES, required=True, label='Dither Sequence', initial='2x2',
                help_text="The pattern to execute your dither points with")
            self.fields[f'c_{j+1}_detector_centering'] = forms.ChoiceField(
                choices=self.DETECTOR_CENTERING_CHOICES, required=True, label='Detector Centering', initial='det_1',
                help_text="Place my target in the center of this detector")
            self.fields[f'c_{j+1}_dither_sequence_random_offset'] = forms.BooleanField(
                required=True, label='Dither Sequence Random Offset', initial=True,
                help_text="Implements a random offset between dither patterns if repeating the dither pattern,"
                " i.e. when sequence repeats > 1")
            self.fields[f'c_{j+1}_repeat_duration'].widget = forms.HiddenInput()
            for i in range(self.facility_settings.get_setting('max_instrument_configs')):
                self.fields[f'c_{j+1}_ic_{i+1}_coadds'] = forms.IntegerField(
                    min_value=1, max_value=100, label='Coadds', initial=1,
                    help_text="This reduces data volume with short integration times necessary for broadband H and Ks"
                    " observations. Coadding is digital summation of the images to avoid long integrations that could"
                    " cause saturation of the detector.",
                    widget=forms.TextInput(attrs={'placeholder': 'Number'}), required=True)
                self.fields[f'c_{j+1}_ic_{i+1}_sequence_repeats'] = forms.IntegerField(
                    min_value=1, max_value=100, label='Sequence Repeats', initial=1,
                    help_text="The number of times to repeat the dither sequence",
                    widget=forms.TextInput(attrs={'placeholder': 'Number'}), required=True)

    def form_name(self):
        return 'blanco'

    def instrument_config_layout_class(self):
        return BLANCOInstrumentConfigLayout

    def configuration_layout_class(self):
        return BLANCOConfigurationLayout

    def advanced_expansions_layout_class(self):
        return BLANCOAdvancedExpansionLayout

    def get_instruments(self):
        instruments = super()._get_instruments()
        return {
            code: instrument for (code, instrument) in instruments.items() if (
                'IMAGE' == instrument['type'] and 'BLANCO' in code)
        }

    def configuration_type_choices(self):
        return [('EXPOSE', 'Exposure'), ('STANDARD', 'Standard')]

    def _build_configuration(self, build_id):
        configuration = super()._build_configuration(build_id)
        # Now parse out the fields that need to be in extra params here
        if configuration:
            configuration['extra_params'] = {
                'dither_value': self.cleaned_data[f'c_{build_id}_dither_value'],
                'dither_sequence': self.cleaned_data[f'c_{build_id}_dither_sequence'],
                'detector_centering': self.cleaned_data[f'c_{build_id}_detector_centering'],
                'dither_sequence_random_offset': self.cleaned_data[f'c_{build_id}_dither_sequence_random_offset']
            }
        return configuration

    def _build_instrument_config(self, instrument_type, configuration_id, instrument_config_id):
        instrument_config = super()._build_instrument_config(instrument_type, configuration_id, instrument_config_id)
        # Now fill in the extra_params fields here
        if instrument_config:
            instrument_config['extra_params'] = {
                'coadds': self.cleaned_data[f'c_{configuration_id}_ic_{instrument_config_id}_coadds'],
                'sequence_repeats': self.cleaned_data[
                    f'c_{configuration_id}_ic_{instrument_config_id}_sequence_repeats'
                ]
            }
        return instrument_config


class BLANCOFacility(LCOFacility):
    """
    The ``BLANCOFacility`` is the interface to the BLANCO Telescope. For information regarding BLANCO observing and the
    available parameters, please see:
    https://noirlab.edu/science/observing-noirlab/observing-ctio/cerro-tololo/observing-blanco.

    Please note that BLANCO is only available in AEON-mode. It also uses the LCO API key, so to use this module, the
    LCO dictionary in FACILITIES in `settings.py` will need to be completed.

    .. code-block:: python
        :caption: settings.py

        FACILITIES = {
            'BLANCO': {
                'portal_url': 'https://observe.lco.global',
                'api_key': os.getenv('LCO_API_KEY'),
            },
        }

    """
    name = 'BLANCO'
    observation_forms = {
        'IMAGING': BLANCOImagingObservationForm
    }

    def __init__(self, facility_settings=BLANCOSettings("BLANCO")):
        super().__init__(facility_settings=facility_settings)

    def get_form(self, observation_type):
        return self.observation_forms.get(observation_type, BLANCOImagingObservationForm)
