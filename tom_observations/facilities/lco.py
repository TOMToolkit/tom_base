from datetime import datetime, timedelta
import logging

from crispy_forms.bootstrap import AppendedText, PrependedText, AccordionGroup
from crispy_forms.layout import Column, Div, HTML, Layout, Row, MultiWidgetField, Fieldset
from dateutil.parser import parse
from django import forms
from django.conf import settings

from tom_observations.cadence import CadenceForm
from tom_observations.facilities.ocs import (OCSTemplateBaseForm, OCSFullObservationForm, OCSBaseObservationForm,
                                             OCSConfigurationLayout, OCSInstrumentConfigLayout, OCSSettings,
                                             OCSFacility)
from tom_observations.widgets import FilterField

logger = logging.getLogger(__name__)


class LCOSettings(OCSSettings):
    """ LCO Specific settings
    """
    default_settings = {
        'portal_url': 'https://observe.lco.global',
        'archive_url': 'https://archive-api.lco.global/',
        'api_key': '',
        'max_instrument_configs': 5,
        'max_configurations': 5
    }
    # These class variables describe default help text for a variety of OCS fields.
    # Override them as desired for a specific OCS implementation.
    end_help = """
        Try the
        <a href="https://lco.global/observatory/visibility/" target="_blank">
            Target Visibility Calculator.
        </a>
    """

    instrument_type_help = """
        <a href="https://lco.global/observatory/instruments/" target="_blank">
            More information about LCO instruments.
        </a>
    """

    max_airmass_help = """
        Advice on
        <a href="https://lco.global/documentation/airmass-limit" target="_blank">
            setting the airmass limit.
        </a>
    """

    exposure_time_help = """
        Try the
        <a href="https://exposure-time-calculator.lco.global/" target="_blank">
            online Exposure Time Calculator.
        </a>
    """

    rotator_mode_help = """
        Only for FLOYDS.
    """

    rotator_angle_help = """
        Rotation angle of slit. Only for Floyds `Slit Position Angle` rotator mode.
    """

    fractional_ephemeris_rate_help = """
        <em>Fractional Ephemeris Rate.</em> Will track with target motion if left blank. <br/>
        <b><em>Caution:</em></b> Setting any value other than "1" will cause the target to slowly drift from the central
        pointing. This could result in the target leaving the field of view for rapid targets, and/or
        long observation blocks. <br/>
    """

    muscat_exposure_mode_help = """
        Synchronous syncs the start time of exposures on all 4 cameras while asynchronous takes
        exposures as quickly as possible on each camera.
    """

    repeat_duration_help = """
        The requested duration for this configuration to be repeated within.
        Only applicable to <em>* Sequence</em> configuration types.
    """

    static_cadencing_help = """
        <em>Static cadence parameters.</em> Leave blank if no cadencing is desired.
        For information on static cadencing with LCO,
        <a href="https://lco.global/documentation/" target="_blank">
            check the Observation Portal getting started guide, starting on page 27.
        </a>
    """

    def __init__(self, facility_name='LCO'):
        super().__init__(facility_name=facility_name)

    def get_fits_facility_header_value(self):
        """ Should return the expected value in the fits facility header for data from this facility
        """
        return 'LCOGT'

    def get_sites(self):
        return {
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

    def get_weather_urls(self):
        return {
            'code': self.facility_name,
            'sites': [
                {
                    'code': site['sitecode'],
                    'weather_url': f'https://weather.lco.global/#/{site["sitecode"]}'
                }
                for site in self.get_sites().values()]
        }


class LCOTemplateBaseForm(OCSTemplateBaseForm):
    def __init__(self, *args, **kwargs):
        if 'facility_settings' not in kwargs:
            kwargs['facility_settings'] = LCOSettings("LCO")
        super().__init__(*args, **kwargs)

    def all_optical_element_choices(self, use_code_only=False):
        return sorted(set([
            (f['code'], f['code'] if use_code_only else f['name']) for ins in self.get_instruments().values() for f in
            ins['optical_elements'].get('filters', []) + ins['optical_elements'].get('slits', []) if f['schedulable']
        ]), key=lambda filter_tuple: filter_tuple[1])


class LCOConfigurationLayout(OCSConfigurationLayout):
    def get_final_accordion_items(self, instance):
        """ Override in the subclasses to add items at the end of the accordion group
        """
        return AccordionGroup('Fractional Ephemeris Rate',
                              Div(
                                  HTML(f'''<br/><p>{self.facility_settings.fractional_ephemeris_rate_help}</p>''')
                              ),
                              Div(
                                  f'c_{instance}_fractional_ephemeris_rate',
                                  css_class='form-col'
                              )
                              )


class MuscatConfigurationLayout(LCOConfigurationLayout):
    def _get_target_override(self, instance):
        if instance == 1:
            return (
                Div(
                    f'c_{instance}_guide_mode',
                    css_class='form-row'
                )
            )
        else:
            return (
                Div(
                    Div(
                        f'c_{instance}_guide_mode',
                        css_class='col'
                    ),
                    Div(
                        f'c_{instance}_target_override',
                        css_class='col'
                    ),
                    css_class='form-row'
                )
            )


class SpectralConfigurationLayout(LCOConfigurationLayout):
    def _get_target_override(self, instance):
        if instance == 1:
            return (
                Div(
                    f'c_{instance}_acquisition_mode',
                    css_class='form-row'
                )
            )
        else:
            return (
                Div(
                    Div(
                        f'c_{instance}_acquisition_mode',
                        css_class='col'
                    ),
                    Div(
                        f'c_{instance}_target_override',
                        css_class='col'
                    ),
                    css_class='form-row'
                )
            )


class MuscatInstrumentConfigLayout(OCSInstrumentConfigLayout):
    def _get_ic_layout(self, config_instance, instance, oe_groups):
        return (
            Div(
                Div(
                    f'c_{config_instance}_ic_{instance}_exposure_mode',
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
                    f'c_{config_instance}_ic_{instance}_readout_mode',
                    css_class='col'
                ),
                css_class='form-row'
            ),
            Fieldset("Exposure Times",
                     HTML('''<p>Select the exposure time for each channel.</p>'''),
                     Div(
                         Div(
                             f'c_{config_instance}_ic_{instance}_exposure_time_g',
                             css_class='col'
                         ),
                         Div(
                             f'c_{config_instance}_ic_{instance}_exposure_time_i',
                             css_class='col'
                         ),
                         css_class='form-row'
                     ),
                     Div(
                         Div(
                             f'c_{config_instance}_ic_{instance}_exposure_time_r',
                             css_class='col'
                         ),
                         Div(
                             f'c_{config_instance}_ic_{instance}_exposure_time_z',
                             css_class='col'
                         ),
                         css_class='form-row'
                     )
                     ),
            *self._get_oe_groups_layout(config_instance, instance, oe_groups)
        )


class SpectralInstrumentConfigLayout(OCSInstrumentConfigLayout):
    def _get_ic_layout(self, config_instance, instance, oe_groups):
        return (
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


class LCOOldStyleObservationForm(OCSBaseObservationForm):
    """
    The LCOOldStyleObservationForm provides the backwards compatibility for the Imaging and Spectral Sequence
    forms to remain the same as they were previously despite the upgrades to the other LCO forms.
    """
    exposure_count = forms.IntegerField(min_value=1)
    min_lunar_distance = forms.IntegerField(min_value=0, label='Minimum Lunar Distance', required=False)
    fractional_ephemeris_rate = forms.FloatField(min_value=0.0, max_value=1.0,
                                                 label='Fractional Ephemeris Rate',
                                                 help_text='Value between 0 (Sidereal Tracking) '
                                                           'and 1 (Target Tracking). If blank, Target Tracking.',
                                                 required=False)

    def __init__(self, *args, **kwargs):
        if 'facility_settings' not in kwargs:
            kwargs['facility_settings'] = LCOSettings("LCO")
        super().__init__(*args, **kwargs)
        self.fields['exposure_time'] = forms.FloatField(
            min_value=0.1, widget=forms.TextInput(attrs={'placeholder': 'Seconds'}),
            help_text=self.facility_settings.exposure_time_help
        )
        self.fields['max_airmass'] = forms.FloatField(help_text=self.facility_settings.max_airmass_help, min_value=0)
        self.fields['max_lunar_phase'] = forms.FloatField(
            help_text=self.facility_settings.max_lunar_phase_help, min_value=0,
            max_value=1.0, label='Maximum Lunar Phase', required=False
        )
        self.fields['filter'] = forms.ChoiceField(choices=self.all_optical_element_choices())
        self.fields['instrument_type'] = forms.ChoiceField(choices=self.instrument_choices())

        if isinstance(self, CadenceForm):
            self.helper.layout.insert(2, self.cadence_layout())

    def layout(self):
        return Div(
            Div(
                Div(
                    'name',
                    css_class='col'
                ),
                Div(
                    'proposal',
                    css_class='col'
                ),
                css_class='form-row'
            ),
            Div(
                Div(
                    'observation_mode',
                    css_class='col'
                ),
                Div(
                    'ipp_value',
                    css_class='col'
                ),
                css_class='form-row'
            ),
            Div(
                Div(
                    'optimization_type',
                    css_class='col'
                ),
                Div(
                    'configuration_repeats',
                    css_class='col'
                ),
                css_class='form-row'
            ),
            Div(
                Div(
                    'start',
                    css_class='col'
                ),
                Div(
                    'end',
                    css_class='col'
                ),
                css_class='form-row'
            ),
            Div(
                Div(
                    'exposure_count',
                    css_class='col'
                ),
                Div(
                    'exposure_time',
                    css_class='col'
                ),
                css_class='form-row'
            ),
            Div(
                Div(
                    'filter',
                    css_class='col'
                ),
                Div(
                    'max_airmass',
                    css_class='col'
                ),
                css_class='form-row'
            ),
            Div(
                Div(
                    'min_lunar_distance',
                    css_class='col'
                ),
                Div(
                    'max_lunar_phase',
                    css_class='col'
                ),
                css_class='form-row'
            )
        )

    def get_instruments(self):
        """Filter the instruments from the OCSBaseObservationForm.get_instruments()
        (i.e. the super class) in an LCO-specifc way.
        """
        instruments = super().get_instruments()
        filtered_instruments = {
            code: instrument
            for (code, instrument) in instruments.items()
            if (instrument['type'] in ['IMAGE', 'SPECTRA'] and
                ('MUSCAT' not in code and 'SOAR' not in code))
        }
        return filtered_instruments

    def all_optical_element_choices(self, use_code_only=False):
        return sorted(set([
            (f['code'], f['code'] if use_code_only else f['name']) for ins in self.get_instruments().values() for f in
            ins['optical_elements'].get('filters', []) + ins['optical_elements'].get('slits', []) if f['schedulable']
        ]), key=lambda filter_tuple: filter_tuple[1])

    def _build_target_extra_params(self, configuration_id=1):
        # if a fractional_ephemeris_rate has been specified, add it as an extra_param
        # to the target_fields
        if 'fractional_ephemeris_rate' in self.cleaned_data:
            return {'fractional_ephemeris_rate': self.cleaned_data['fractional_ephemeris_rate']}
        return {}

    def _build_instrument_configs(self):
        instrument_config = {
            'exposure_count': self.cleaned_data['exposure_count'],
            'exposure_time': self.cleaned_data['exposure_time'],
            'optical_elements': {
                'filter': self.cleaned_data['filter']
            }
        }
        instrument_configs = [instrument_config]
        return instrument_configs


class LCOFullObservationForm(OCSFullObservationForm):
    def __init__(self, *args, **kwargs):
        if 'facility_settings' not in kwargs:
            kwargs['facility_settings'] = LCOSettings("LCO")
        if 'data' in kwargs:
            # convert data argument field names to the proper fields. Data is assumed to be observation payload format
            kwargs['data'] = self.convert_old_observation_payload_to_fields(kwargs['data'])
        super().__init__(*args, **kwargs)
        for j in range(self.facility_settings.get_setting('max_configurations')):
            self.fields[f'c_{j+1}_fractional_ephemeris_rate'] = forms.FloatField(
                min_value=0.0, max_value=1.0, label='Fractional Ephemeris Rate',
                help_text='Value between 0 (Sidereal Tracking) '
                'and 1 (Target Tracking). If blank, Target Tracking.',
                required=False
            )
        # self.helper.layout = Layout(
        #     self.common_layout,
        #     self.layout(),
        #     self.button_layout()
        # )
        # if isinstance(self, CadenceForm):
        #     self.helper.layout.insert(2, self.cadence_layout())

    def convert_old_observation_payload_to_fields(self, data):
        """ This is a backwards compatibility function to allow us to load old-format observation parameters
            for existing ObservationRecords, which use the old form, but may still need to use the new form
            to submit cadence strategy observations.
        """
        if 'instrument_type' in data:
            data['c_1_instrument_type'] = data['instrument_type']
            del data['instrument_type']
        if 'max_airmass' in data:
            data['c_1_max_airmass'] = data['max_airmass']
            del data['max_airmass']
        if 'min_lunar_distance' in data:
            data['c_1_min_lunar_distance'] = data['min_lunar_distance']
            del data['min_lunar_distance']
        if 'fractional_ephemeris_rate' in data:
            data['c_1_fractional_ephemeris_rate'] = data['fractional_ephemeris_rate']
            del data['fractional_ephemeris_rate']
        if 'exposure_count' in data:
            data['c_1_ic_1_exposure_count'] = data['exposure_count']
            del data['exposure_count']
        if 'exposure_time' in data:
            data['c_1_ic_1_exposure_time'] = data['exposure_time']
            del data['exposure_time']
        if 'filter' in data:
            data['c_1_ic_1_filter'] = data['filter']
            del data['filter']
        return data

    def configuration_layout_class(self):
        return LCOConfigurationLayout

    def _build_target_extra_params(self, configuration_id=1):
        # if a fractional_ephemeris_rate has been specified, add it as an extra_param
        # to the target_fields
        if f'c_{configuration_id}_fractional_ephemeris_rate' in self.cleaned_data:
            return {'fractional_ephemeris_rate': self.cleaned_data[f'c_{configuration_id}_fractional_ephemeris_rate']}
        return {}


class LCOImagingObservationForm(LCOFullObservationForm):
    """
    The LCOImagingObservationForm allows the selection of parameters for observing using LCO's Imagers. The list of
    Imagers and their details can be found here: https://lco.global/observatory/instruments/
    """

    def get_instruments(self):
        instruments = super().get_instruments()
        return {
            code: instrument for (code, instrument) in instruments.items() if (
                'IMAGE' == instrument['type'] and 'MUSCAT' not in code and 'SOAR' not in code)
        }

    def form_name(self):
        return 'image'

    def configuration_type_choices(self):
        return [('EXPOSE', 'Exposure'), ('REPEAT_EXPOSE', 'Exposure Sequence')]


class LCOMuscatImagingObservationForm(LCOFullObservationForm):
    """
    The LCOMuscatImagingObservationForm allows the selection of parameter for observing using LCO's Muscat imaging
    instrument. More information can be found here: https://lco.global/observatory/instruments/muscat3/
    """

    def __init__(self, *args, **kwargs):
        if 'facility_settings' not in kwargs:
            kwargs['facility_settings'] = LCOSettings("LCO")
        super().__init__(*args, **kwargs)
        # Need to add the muscat specific exposure time fields to this form
        for j in range(self.facility_settings.get_setting('max_configurations')):
            self.fields[f'c_{j+1}_guide_mode'] = forms.ChoiceField(
                choices=self.mode_choices('guiding'), required=False, label='Guide Mode')
            for i in range(self.facility_settings.get_setting('max_instrument_configs')):
                self.fields.pop(f'c_{j+1}_ic_{i+1}_exposure_time', None)
                self.fields[f'c_{j+1}_ic_{i+1}_exposure_time_g'] = forms.FloatField(
                    min_value=0.0, label='Exposure Time g',
                    widget=forms.TextInput(attrs={'placeholder': 'Seconds'}), required=False)
                self.fields[f'c_{j+1}_ic_{i+1}_exposure_time_r'] = forms.FloatField(
                    min_value=0.0, label='Exposure Time r',
                    widget=forms.TextInput(attrs={'placeholder': 'Seconds'}), required=False)
                self.fields[f'c_{j+1}_ic_{i+1}_exposure_time_i'] = forms.FloatField(
                    min_value=0.0, label='Exposure Time i',
                    widget=forms.TextInput(attrs={'placeholder': 'Seconds'}), required=False)
                self.fields[f'c_{j+1}_ic_{i+1}_exposure_time_z'] = forms.FloatField(
                    min_value=0.0, label='Exposure Time z',
                    widget=forms.TextInput(attrs={'placeholder': 'Seconds'}), required=False)
                self.fields[f'c_{j+1}_ic_{i+1}_readout_mode'] = forms.ChoiceField(
                    choices=self.mode_choices('readout'), required=False, label='Readout Mode')
                self.fields[f'c_{j+1}_ic_{i+1}_exposure_mode'] = forms.ChoiceField(
                    label='Exposure Mode', required=False,
                    choices=self.mode_choices('exposure'),
                    help_text=self.facility_settings.muscat_exposure_mode_help
                )

    def convert_old_observation_payload_to_fields(self, data):
        data = super().convert_old_observation_payload_to_fields(data)
        if not data:
            return None
        ic_fields = [
            'exposure_time_g', 'exposure_time_r', 'exposure_time_i', 'exposure_time_z', 'exposure_mode',
            'diffuser_g_position', 'diffuser_r_position', 'diffuser_i_position', 'diffuser_z_position'
        ]
        for field in ic_fields:
            if field in data:
                data[f'c_1_ic_1_{field}'] = data[field]
                del data[field]

        if 'guider_mode' in data:
            data['c_1_guide_mode'] = data['guider_mode']
            del data['guider_mode']
        return data

    def form_name(self):
        return 'muscat'

    def instrument_config_layout_class(self):
        return MuscatInstrumentConfigLayout

    def configuration_layout_class(self):
        return MuscatConfigurationLayout

    def get_instruments(self):
        instruments = super().get_instruments()
        return {
            code: instrument for (code, instrument) in instruments.items() if (
                'IMAGE' == instrument['type'] and 'MUSCAT' in code)
        }

    def configuration_type_choices(self):
        return [('EXPOSE', 'Exposure'), ('REPEAT_EXPOSE', 'Exposure Sequence')]

    def _build_guiding_config(self, configuration_id=1):
        guiding_config = super()._build_guiding_config()
        guiding_config['mode'] = self.cleaned_data[f'c_{configuration_id}_guide_mode']
        # Muscat guiding `optional` setting only makes sense set to true from the telescope software perspective
        guiding_config['optional'] = True
        return guiding_config

    def _build_instrument_config(self, instrument_type, configuration_id, instrument_config_id):
        # Refer to the 'MUSCAT instrument configuration' section on this page: https://developers.lco.global/
        if not (self.cleaned_data.get(f'c_{configuration_id}_ic_{instrument_config_id}_exposure_time_g') and
                self.cleaned_data.get(f'c_{configuration_id}_ic_{instrument_config_id}_exposure_time_r') and
                self.cleaned_data.get(f'c_{configuration_id}_ic_{instrument_config_id}_exposure_time_i') and
                self.cleaned_data.get(f'c_{configuration_id}_ic_{instrument_config_id}_exposure_time_z')):
            return None
        instrument_config = {
            'exposure_count': self.cleaned_data[f'c_{configuration_id}_ic_{instrument_config_id}_exposure_count'],
            'exposure_time': max(
                self.cleaned_data[f'c_{configuration_id}_ic_{instrument_config_id}_exposure_time_g'],
                self.cleaned_data[f'c_{configuration_id}_ic_{instrument_config_id}_exposure_time_r'],
                self.cleaned_data[f'c_{configuration_id}_ic_{instrument_config_id}_exposure_time_i'],
                self.cleaned_data[f'c_{configuration_id}_ic_{instrument_config_id}_exposure_time_z']
            ),
            'optical_elements': {},
            'mode': self.cleaned_data[f'c_{configuration_id}_ic_{instrument_config_id}_readout_mode'],
            'extra_params': {
                'exposure_mode': self.cleaned_data[f'c_{configuration_id}_ic_{instrument_config_id}_exposure_mode'],
                'exposure_time_g': self.cleaned_data[f'c_{configuration_id}_ic_{instrument_config_id}_exposure_time_g'],
                'exposure_time_r': self.cleaned_data[f'c_{configuration_id}_ic_{instrument_config_id}_exposure_time_r'],
                'exposure_time_i': self.cleaned_data[f'c_{configuration_id}_ic_{instrument_config_id}_exposure_time_i'],
                'exposure_time_z': self.cleaned_data[f'c_{configuration_id}_ic_{instrument_config_id}_exposure_time_z'],
            }
        }
        for oe_group in self.get_optical_element_groups():
            instrument_config['optical_elements'][oe_group] = self.cleaned_data.get(
                f'c_{configuration_id}_ic_{instrument_config_id}_{oe_group}')

        return instrument_config


class LCOSpectroscopyObservationForm(LCOFullObservationForm):
    """
    The LCOSpectroscopyObservationForm allows the selection of parameters for observing using LCO's Spectrographs. The
    list of spectrographs and their details can be found here: https://lco.global/observatory/instruments/
    """

    def __init__(self, *args, **kwargs):
        if 'facility_settings' not in kwargs:
            kwargs['facility_settings'] = LCOSettings("LCO")
        super().__init__(*args, **kwargs)
        for j in range(self.facility_settings.get_setting('max_configurations')):
            self.fields[f'c_{j+1}_acquisition_mode'] = forms.ChoiceField(
                choices=self.mode_choices('acquisition', use_code_only=True), required=False, label='Acquisition Mode')
            for i in range(self.facility_settings.get_setting('max_instrument_configs')):
                self.fields[f'c_{j+1}_ic_{i+1}_rotator_mode'] = forms.ChoiceField(
                    choices=self.mode_choices('rotator'), label='Rotator Mode', required=False,
                    help_text=self.facility_settings.rotator_mode_help)
                self.fields[f'c_{j+1}_ic_{i+1}_rotator_angle'] = forms.FloatField(
                    min_value=0.0, initial=0.0,
                    help_text=self.facility_settings.rotator_angle_help,
                    label='Rotator Angle', required=False
                )
                # Add None option and help text for SOAR Gratings
                if self.fields.get(f'c_{j+1}_ic_{i+1}_grating', None):
                    self.fields[f'c_{j+1}_ic_{i+1}_grating'].help_text = 'Only for SOAR'
                    self.fields[f'c_{j+1}_ic_{i+1}_grating'].choices.insert(0, ('None', 'None'))
                if self.fields.get(f'c_{j+1}_ic_{i+1}_slit', None):
                    self.fields[f'c_{j+1}_ic_{i+1}_slit'].help_text = 'Only for Floyds'

    def convert_old_observation_payload_to_fields(self, data):
        data = super().convert_old_observation_payload_to_fields(data)
        if not data:
            return None
        if 'rotator_angle' in data:
            data['c_1_ic_1_rotator_angle'] = data['rotator_angle']
            if data['rotator_angle']:
                data['c_1_ic_1_rotator_mode'] = 'SKY'
            del data['rotator_angle']
        if 'c_1_ic_1_filter' in data:
            data['c_1_ic_1_slit'] = data['c_1_ic_1_filter']
            del data['c_1_ic_1_filter']

        return data

    def get_instruments(self):
        instruments = super().get_instruments()
        return {code: instrument for (code, instrument) in instruments.items() if ('SPECTRA' == instrument['type'])}

    def form_name(self):
        return 'spectra'

    def instrument_config_layout_class(self):
        return SpectralInstrumentConfigLayout

    def configuration_layout_class(self):
        return SpectralConfigurationLayout

    def configuration_type_choices(self):
        return [
            ('SPECTRUM', 'Spectrum'),
            ('REPEAT_SPECTRUM', 'Spectrum Sequence'),
            ('ARC', 'Arc'),
            ('LAMP_FLAT', 'Lamp Flat')
        ]

    def _build_acquisition_config(self, configuration_id=1):
        acquisition_config = {'mode': self.cleaned_data[f'c_{configuration_id}_acquisition_mode']}

        return acquisition_config

    def _build_configuration(self, build_id):
        configuration = super()._build_configuration(build_id)
        if not configuration:
            return None
        # If NRES, adjust the configuration types to match nres types
        if 'NRES' in configuration['instrument_type'].upper():
            if configuration['type'] == 'SPECTRUM':
                configuration['type'] = 'NRES_SPECTRUM'
            elif configuration['type'] == 'REPEAT_SPECTRUM':
                configuration['type'] = 'REPEAT_NRES_SPECTRUM'

        return configuration

    def _build_instrument_config(self, instrument_type, configuration_id, instrument_config_id):
        instrument_config = super()._build_instrument_config(instrument_type, configuration_id, instrument_config_id)
        if not instrument_config:
            return None
        # If floyds, add the rotator mode and angle in
        if 'FLOYDS' in instrument_type.upper() or 'SOAR' in instrument_type.upper():
            instrument_config['rotator_mode'] = self.cleaned_data[
                f'c_{configuration_id}_ic_{instrument_config_id}_rotator_mode'
                ]
            if instrument_config['rotator_mode'] == 'SKY':
                instrument_config['extra_params'] = {'rotator_angle': self.cleaned_data.get(
                    f'c_{configuration_id}_ic_{instrument_config_id}_rotator_angle', 0)}
            if 'FLOYDS' in instrument_type.upper():
                # Remove grating from FLOYDS requests
                instrument_config['optical_elements'].pop('grating', None)
        # Clear out the optical elements for NRES
        elif 'NRES' in instrument_type.upper():
            instrument_config['optical_elements'] = {}

        return instrument_config


class LCOPhotometricSequenceForm(LCOOldStyleObservationForm):
    """
    The LCOPhotometricSequenceForm provides a form offering a subset of the parameters in the LCOImagingObservationForm.
    The form is modeled after the Supernova Exchange application's Photometric Sequence Request Form, and allows the
    configuration of multiple filters, as well as a more intuitive proactive cadence form.
    """
    valid_instruments = ['1M0-SCICAM-SINISTRO', '0M4-SCICAM-SBIG', '2M0-SPECTRAL-AG']
    valid_filters = ['U', 'B', 'V', 'R', 'I', 'up', 'gp', 'rp', 'ip', 'zs', 'w', 'unknown']
    cadence_frequency = forms.IntegerField(required=True, help_text='in hours')

    def __init__(self, *args, **kwargs):
        if 'facility_settings' not in kwargs:
            kwargs['facility_settings'] = LCOSettings("LCO")
        if 'initial' in kwargs:
            # Because we use a FilterField custom field here that combines three fields, we must
            # convert those fields when they are passed in so validation doesn't depopulate the fields
            kwargs['initial'] = self.convert_filter_fields(kwargs['initial'])
        super().__init__(*args, **kwargs)

        # Add fields for each available filter as specified in the filters property
        for filter_code, filter_name in self.all_optical_element_choices():
            self.fields[filter_code] = FilterField(label=filter_name, required=False)

        # Massage cadence form to be SNEx-styled
        self.fields['cadence_strategy'] = forms.ChoiceField(
            choices=[('', 'Once in the next'), ('ResumeCadenceAfterFailureStrategy', 'Repeating every')],
            required=False,
        )
        for field_name in ['exposure_time', 'exposure_count', 'filter']:
            self.fields.pop(field_name)
        if self.fields.get('groups'):
            self.fields['groups'].label = 'Data granted to'
        for field_name in ['start', 'end']:
            self.fields[field_name].widget = forms.HiddenInput()
            self.fields[field_name].required = False

        self.helper.layout = Layout(
            Row(
                Column('name'),
                Column('cadence_strategy'),
                Column('cadence_frequency'),
            ),
            Layout('facility', 'target_id', 'observation_type'),
            self.layout(),
            self.button_layout()
        )

    def _build_instrument_configs(self):
        """
        Because the photometric sequence form provides form inputs for 10 different filters, they must be
        constructed into a list of instrument configurations as per the LCO API. This method constructs the
        instrument configurations in the appropriate manner.
        """
        instrument_configs = []
        for filter_code, _ in self.all_optical_element_choices():
            if len(self.cleaned_data[filter_code]) > 0:
                instrument_configs.append({
                    'exposure_count': self.cleaned_data[filter_code][1],
                    'exposure_time': self.cleaned_data[filter_code][0],
                    'optical_elements': {
                        'filter': filter_code
                    }
                })

        return instrument_configs

    def convert_filter_fields(self, initial):
        if not initial:
            return initial
        for filter_name in self.valid_filters:
            if f'{filter_name}_0' in initial or f'{filter_name}_1' in initial or f'{filter_name}_2' in initial:
                initial[f'{filter_name}'] = [
                    initial[f'{filter_name}_0'],
                    initial[f'{filter_name}_1'],
                    initial[f'{filter_name}_2']
                ]
        return initial

    def clean_start(self):
        """
        Unless included in the submission, set the start time to now.
        """
        start = self.cleaned_data.get('start')
        if not start:  # Start is in cleaned_data as an empty string if it was not submitted, so check falsiness
            start = datetime.strftime(datetime.now(), '%Y-%m-%dT%H:%M:%S')
        return start

    def clean_end(self):
        """
        Override clean_end in order to avoid the superclass attempting to date-parse an empty string.
        """
        return self.cleaned_data.get('end')

    def clean(self):
        """
        This clean method does the following:
            - Adds an end time that corresponds with the cadence frequency
        """
        cleaned_data = super().clean()
        start = cleaned_data.get('start')
        cleaned_data['end'] = datetime.strftime(parse(start) + timedelta(hours=cleaned_data['cadence_frequency']),
                                                '%Y-%m-%dT%H:%M:%S')

        return cleaned_data

    def instrument_choices(self):
        """
        This method returns only the instrument choices available in the current SNEx photometric sequence form.
        """
        return sorted([(k, v['name'])
                       for k, v in self._get_instruments().items()
                       if k in LCOPhotometricSequenceForm.valid_instruments],
                      key=lambda inst: inst[1])

    def all_optical_element_choices(self, use_code_only=False):
        return sorted(set([
            (f['code'], f['name']) for ins in self._get_instruments().values() for f in
            ins['optical_elements'].get('filters', [])
            if f['code'] in LCOPhotometricSequenceForm.valid_filters]),
            key=lambda filter_tuple: filter_tuple[1])

    def cadence_layout(self):
        return Layout(
            Row(
                Column('cadence_type'), Column('cadence_frequency')
            )
        )

    def layout(self):
        if settings.TARGET_PERMISSIONS_ONLY:
            groups = Div()
        else:
            groups = Row('groups')

        # Add filters to layout
        filter_layout = Layout(
            Row(
                Column(HTML('Exposure Time')),
                Column(HTML('No. of Exposures')),
                Column(HTML('Block No.')),
            )
        )
        for filter_code, _ in self.all_optical_element_choices():
            filter_layout.append(Row(MultiWidgetField(filter_code, attrs={'min': 0})))

        return Row(
            Column(
                filter_layout,
                css_class='col-md-6'
            ),
            Column(
                Row('max_airmass'),
                Row(
                    PrependedText('min_lunar_distance', '>')
                ),
                Row('instrument_type'),
                Row('proposal'),
                Row('observation_mode'),
                Row('ipp_value'),
                groups,
                css_class='col-md-6'
            ),
        )


class LCOSpectroscopicSequenceForm(LCOOldStyleObservationForm):
    site = forms.ChoiceField(choices=(('any', 'Any'), ('ogg', 'Hawaii'), ('coj', 'Australia')))
    acquisition_radius = forms.FloatField(min_value=0, required=False)
    guider_mode = forms.ChoiceField(choices=[('on', 'On'), ('off', 'Off'), ('optional', 'Optional')], required=True)
    guider_exposure_time = forms.IntegerField(min_value=0)
    cadence_frequency = forms.IntegerField(required=True,
                                           widget=forms.NumberInput(attrs={'placeholder': 'Hours'}))

    def __init__(self, *args, **kwargs):
        if 'facility_settings' not in kwargs:
            kwargs['facility_settings'] = LCOSettings("LCO")
        super().__init__(*args, **kwargs)

        # Massage cadence form to be SNEx-styled
        self.fields['name'].label = ''
        self.fields['name'].widget.attrs['placeholder'] = 'Name'
        self.fields['min_lunar_distance'].widget.attrs['placeholder'] = 'Degrees'
        self.fields['cadence_strategy'] = forms.ChoiceField(
            choices=[('', 'Once in the next'), ('ResumeCadenceAfterFailureStrategy', 'Repeating every')],
            required=False,
            label=''
        )
        self.fields['cadence_frequency'].label = ''

        # Remove start and end because those are determined by the cadence
        for field_name in ['instrument_type']:
            self.fields.pop(field_name)
        if self.fields.get('groups'):
            self.fields['groups'].label = 'Data granted to'
        for field_name in ['start', 'end']:
            self.fields[field_name].widget = forms.HiddenInput()
            self.fields[field_name].required = False

        self.helper.layout = Layout(
            Div(
                Column('name'),
                Column('cadence_strategy'),
                Column(AppendedText('cadence_frequency', 'Hours')),
                css_class='form-row'
            ),
            Layout('facility', 'target_id', 'observation_type'),
            self.layout(),
            self.button_layout()
        )

    def _build_configuration(self):
        configuration = super()._build_configuration()
        configuration['type'] = 'SPECTRUM'
        return configuration

    def _build_instrument_configs(self):
        instrument_configs = super()._build_instrument_configs()
        instrument_configs[0]['optical_elements'].pop('filter')
        instrument_configs[0]['optical_elements']['slit'] = self.cleaned_data['filter']

        return instrument_configs

    def _build_acquisition_config(self):
        acquisition_config = super()._build_acquisition_config()
        # SNEx uses WCS mode if no acquisition radius is specified, and BRIGHTEST otherwise
        if not self.cleaned_data['acquisition_radius']:
            acquisition_config['mode'] = 'WCS'
        else:
            acquisition_config['mode'] = 'BRIGHTEST'
            acquisition_config['extra_params'] = {
                'acquire_radius': self.cleaned_data['acquisition_radius']
            }

        return acquisition_config

    def _build_guiding_config(self):
        guiding_config = super()._build_guiding_config()
        guiding_config['mode'] = 'ON' if self.cleaned_data['guider_mode'] in ['on', 'optional'] else 'OFF'
        guiding_config['optional'] = 'true' if self.cleaned_data['guider_mode'] == 'optional' else 'false'
        return guiding_config

    def _build_location(self):
        location = super()._build_location()
        site = self.cleaned_data['site']
        if site != 'any':
            location['site'] = site
        return location

    def clean_start(self):
        """
        Unless included in the submission, set the start time to now.
        """
        start = self.cleaned_data.get('start')
        if not start:  # Start is in cleaned_data as an empty string if it was not submitted, so check falsiness
            start = datetime.strftime(datetime.now(), '%Y-%m-%dT%H:%M:%S')
        return start

    def clean_end(self):
        """
        Override clean_end in order to avoid the superclass attempting to date-parse an empty string.
        """
        return self.cleaned_data.get('end')

    def clean(self):
        """
        This clean method does the following:
            - Hardcodes instrument type as "2M0-FLOYDS-SCICAM" because it's the only instrument this form uses
            - Adds a start time of "right now", as the spectroscopic sequence form does not allow for specification
              of a start time.
            - Adds an end time that corresponds with the cadence frequency
            - Adds the cadence strategy to the form if "repeat" was the selected "cadence_type". If "once" was
              selected, the observation is submitted as a single observation.
        """
        cleaned_data = super().clean()
        cleaned_data['instrument_type'] = '2M0-FLOYDS-SCICAM'  # SNEx only submits spectra to FLOYDS
        start = cleaned_data.get('start')
        cleaned_data['end'] = datetime.strftime(parse(start) + timedelta(hours=cleaned_data['cadence_frequency']),
                                                '%Y-%m-%dT%H:%M:%S')

        return cleaned_data

    def instrument_choices(self):
        # SNEx only uses the Spectroscopic Sequence Form with FLOYDS
        # This doesn't need to be sorted because it will only return one instrument
        return [(k, v['name'])
                for k, v in self._get_instruments().items()
                if k == '2M0-FLOYDS-SCICAM']

    def all_optical_element_choices(self, use_code_only=False):
        return sorted(set([
            (f['code'], f['name']) for name, ins in self._get_instruments().items() for f in
            ins['optical_elements'].get('slits', []) if name == '2M0-FLOYDS-SCICAM'
        ]), key=lambda filter_tuple: filter_tuple[1])

    def layout(self):
        if settings.TARGET_PERMISSIONS_ONLY:
            groups = Div()
        else:
            groups = Row('groups')
        return Div(
            Row('exposure_count'),
            Row('exposure_time'),
            Row('max_airmass'),
            Row(PrependedText('min_lunar_distance', '>')),
            Row('site'),
            Row('filter'),
            Row('acquisition_radius'),
            Row('guider_mode'),
            Row('guider_exposure_time'),
            Row('proposal'),
            Row('observation_mode'),
            Row('ipp_value'),
            groups,
        )


class LCOFacility(OCSFacility):
    """
    The ``LCOFacility`` is the interface to the Las Cumbres Observatory Observation Portal. For information regarding
    LCO observing and the available parameters, please see https://observe.lco.global/help/.
    """
    name = 'LCO'
    observation_forms = {
        'IMAGING': LCOImagingObservationForm,
        'MUSCAT_IMAGING': LCOMuscatImagingObservationForm,
        'SPECTRA': LCOSpectroscopyObservationForm,
        'PHOTOMETRIC_SEQUENCE': LCOPhotometricSequenceForm,
        'SPECTROSCOPIC_SEQUENCE': LCOSpectroscopicSequenceForm
    }

    def __init__(self, facility_settings=LCOSettings('LCO')):
        super().__init__(facility_settings=facility_settings)

    # TODO: this should be called get_form_class
    def get_form(self, observation_type):
        return self.observation_forms.get(observation_type, LCOOldStyleObservationForm)

    # TODO: this should be called get_template_form_class
    def get_template_form(self, observation_type):
        return LCOTemplateBaseForm
