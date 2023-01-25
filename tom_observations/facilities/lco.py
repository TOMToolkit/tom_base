from datetime import datetime, timedelta
import logging
import requests
from urllib.parse import urlencode

from astropy import units as u
from crispy_forms.bootstrap import AppendedText, PrependedText, Accordion, AccordionGroup, TabHolder, Tab, Alert
from crispy_forms.layout import Column, Div, HTML, Layout, Row, MultiWidgetField, Fieldset, Submit, ButtonHolder
from dateutil.parser import parse
from django import forms
from django.conf import settings
from django.core.cache import cache

from tom_common.exceptions import ImproperCredentialsException
from tom_observations.cadence import CadenceForm
from tom_observations.facility import BaseRoboticObservationFacility, BaseRoboticObservationForm, get_service_class
from tom_observations.observation_template import GenericTemplateForm
from tom_observations.widgets import FilterField
from tom_targets.models import Target, REQUIRED_NON_SIDEREAL_FIELDS, REQUIRED_NON_SIDEREAL_FIELDS_PER_SCHEME

logger = logging.getLogger(__name__)

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
# Valid observing states at LCO are defined here: https://developers.lco.global/#data-format-definition
VALID_OBSERVING_STATES = [
    'PENDING', 'COMPLETED', 'WINDOW_EXPIRED', 'CANCELED', 'FAILURE_LIMIT_REACHED', 'NOT_ATTEMPTED'
]
PENDING_OBSERVING_STATES = ['PENDING']
SUCCESSFUL_OBSERVING_STATES = ['COMPLETED']
FAILED_OBSERVING_STATES = ['WINDOW_EXPIRED', 'CANCELED', 'FAILURE_LIMIT_REACHED', 'NOT_ATTEMPTED']
TERMINAL_OBSERVING_STATES = SUCCESSFUL_OBSERVING_STATES + FAILED_OBSERVING_STATES

# Units of flux and wavelength for converting to Specutils Spectrum1D objects
FLUX_CONSTANT = (1e-15 * u.erg) / (u.cm ** 2 * u.second * u.angstrom)
WAVELENGTH_UNITS = u.angstrom

# FITS header keywords used for data processing
FITS_FACILITY_KEYWORD = 'ORIGIN'
FITS_FACILITY_KEYWORD_VALUE = 'LCOGT'
FITS_FACILITY_DATE_OBS_KEYWORD = 'DATE-OBS'

MAX_INSTRUMENT_CONFIGS = 5
MAX_CONFIGURATIONS = 5

# Functions needed specifically for LCO
# Helpers for LCO fields
ipp_value_help = """
        Value between 0.5 to 2.0.
        <a href="https://lco.global/documents/20/the_new_priority_factor.pdf">
            More information about Intra Proprosal Priority (IPP).
        </a>
"""

observation_mode_help = """
    <a href="https://lco.global/documentation/special-scheduling-modes/">
        More information about Rapid Response mode.
    </a>
"""

optimization_type_help = """
    Scheduling optimization emphasis: Time for ASAP, or Airmass for minimum airmass.
"""

end_help = """
    Try the
    <a href="https://lco.global/observatory/visibility/">
        Target Visibility Calculator.
    </a>
"""

instrument_type_help = """
    <a href="https://lco.global/observatory/instruments/">
        More information about LCO instruments.
    </a>
"""

exposure_time_help = """
    Try the
    <a href="https://exposure-time-calculator.lco.global/">
        online Exposure Time Calculator.
    </a>
"""

max_airmass_help = """
    Advice on
    <a href="https://lco.global/documentation/airmass-limit">
        setting the airmass limit.
    </a>
"""

max_lunar_phase_help = """
    Value between 0 (new moon) and 1 (full moon).
"""

fractional_ephemeris_rate_help = """
    <em>Fractional Ephemeris Rate.</em> Will track with target motion if left blank. <br/>
    <b><em>Caution:</em></b> Setting any value other than "1" will cause the target to slowly drift from the central
    pointing. This could result in the target leaving the field of view for rapid targets, and/or
    long observation blocks. <br/>
"""

static_cadencing_help = """
    <em>Static cadence parameters.</em> Leave blank if no cadencing is desired.
    For information on static cadencing with LCO,
    <a href="https://lco.global/documentation/">
        check the Observation Portal getting started guide, starting on page 27.
    </a>
"""

muscat_exposure_mode_help = """
    Synchronous syncs the start time of exposures on all 4 cameras while asynchronous takes
    exposures as quickly as possible on each camera.
"""

repeat_duration_help = """
    The requested duration for this configuration to be repeated within.
    Only applicable to <em>* Sequence</em> configuration types.
"""


def make_request(*args, **kwargs):
    response = requests.request(*args, **kwargs)
    if 401 <= response.status_code <= 403:
        raise ImproperCredentialsException('LCO: ' + str(response.content))
    elif 400 == response.status_code:
        raise forms.ValidationError(f'LCO: {str(response.content)}')
    response.raise_for_status()
    return response


class LCOBaseForm(forms.Form):
    """ The LCOBaseForm assumes nothing of fields, and just adds helper methods for getting
        data from the LCO portal to other form subclasses.
    """

    def target_group_choices(self):
        target_id = self.data.get('target_id')
        if not target_id:
            target_id = self.initial.get('target_id')
        try:
            target_name = Target.objects.get(pk=target_id).name
            group_targets = Target.objects.filter(targetlist__targets__pk=target_id).exclude(
                pk=target_id).order_by('name').distinct().values_list('pk', 'name')
            return [(target_id, target_name)] + list(group_targets)
        except Target.DoesNotExist:
            return []

    @staticmethod
    def _get_instruments():
        cached_instruments = cache.get('lco_instruments')

        if not cached_instruments:
            response = make_request(
                'GET',
                PORTAL_URL + '/api/instruments/',
                headers={'Authorization': 'Token {0}'.format(LCO_SETTINGS['api_key'])}
            )
            cached_instruments = {k: v for k, v in response.json().items() if 'SOAR' not in k}
            cache.set('lco_instruments', cached_instruments, 3600)

        return cached_instruments

    @staticmethod
    def instrument_to_type(instrument_type):
        if 'FLOYDS' in instrument_type:
            return 'SPECTRUM'
        elif 'NRES' in instrument_type:
            return 'NRES_SPECTRUM'
        else:
            return 'EXPOSE'

    def get_instruments(self):
        return LCOBaseForm._get_instruments()

    def instrument_choices(self):
        return sorted([(k, v['name']) for k, v in self.get_instruments().items()], key=lambda inst: inst[1])

    def mode_choices(self, mode_type, use_code_only=False):
        return sorted(set([
            (f['code'], f['code'] if use_code_only else f['name']) for ins in self.get_instruments().values() for f in
            ins.get('modes', {}).get(mode_type, {}).get('modes', [])
        ]), key=lambda filter_tuple: filter_tuple[1])

    def filter_choices(self, use_code_only=False):
        return sorted(set([
            (f['code'], f['code'] if use_code_only else f['name']) for ins in self.get_instruments().values() for f in
            ins['optical_elements'].get('filters', []) + ins['optical_elements'].get('slits', []) if f['schedulable']
        ]), key=lambda filter_tuple: filter_tuple[1])

    def filter_choices_for_group(self, oe_group, use_code_only=False):
        return sorted(set([
            (f['code'], f['code'] if use_code_only else f['name']) for ins in self.get_instruments().values() for f in
            ins['optical_elements'].get(oe_group, []) if f.get('schedulable')
        ]), key=lambda filter_tuple: filter_tuple[1])

    def get_optical_element_groups(self):
        oe_groups = set()
        for instrument in self.get_instruments().values():
            for oe_group in instrument['optical_elements'].keys():
                oe_groups.add(oe_group.rstrip('s'))
        return sorted(oe_groups)

    def configuration_type_choices(self):
        all_config_types = set()
        for instrument in self.get_instruments().values():
            config_types = instrument.get('configuration_types', {}).values()
            all_config_types.update(
                {(config_type.get('code'), config_type.get('name'))
                 for config_type in config_types if config_type.get('schedulable')}
            )
        return sorted(all_config_types, key=lambda config_type: config_type[1])

    @staticmethod
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


class LCOTemplateBaseForm(LCOBaseForm):
    ipp_value = forms.FloatField()
    exposure_count = forms.IntegerField(min_value=1)
    exposure_time = forms.FloatField(min_value=0.1)
    max_airmass = forms.FloatField()

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['proposal'] = forms.ChoiceField(choices=self.proposal_choices())
        self.fields['filter'] = forms.ChoiceField(choices=self.filter_choices())
        self.fields['instrument_type'] = forms.ChoiceField(choices=self.instrument_choices())


class AdvancedExpansionsLayout(Layout):
    def __init__(self, form_name, *args, **kwargs):
        super().__init__(
            Accordion(
                *self._get_accordion_group(form_name)
            )
        )

    def _get_accordion_group(self, form_name):
        return (
            AccordionGroup(
                'Cadence / Dither / Mosaic',
                Alert(
                    content="""Using the following sections each result in expanding portions of the Request
                                on submission. You should only combine these if you know what you are doing.
                            """,
                    css_class='alert-warning'
                ),
                TabHolder(
                    Tab('Cadence',
                        Div(
                            HTML(f'''<br/><p>{static_cadencing_help}</p>'''),
                        ),
                        Div(
                            Div(
                                'period',
                                css_class='col'
                            ),
                            Div(
                                'jitter',
                                css_class='col'
                            ),
                            css_class='form-row'
                        ),
                        css_id=f'{form_name}_cadence'
                        ),
                    Tab('Dithering',
                        Alert(
                            content="Dithering will only be applied if you have a single Configuration specified.",
                            css_class='alert-warning'
                        ),
                        Div(
                            Div(
                                'dither_pattern',
                                css_class='col'
                            ),
                            Div(
                                'dither_num_points',
                                css_class='col'
                            ),
                            css_class='form-row'
                        ),
                        Div(
                            Div(
                                'dither_point_spacing',
                                css_class='col'
                            ),
                            Div(
                                'dither_line_spacing',
                                css_class='col'
                            ),
                            css_class='form-row'
                        ),
                        Div(
                            Div(
                                'dither_num_rows',
                                css_class='col'
                            ),
                            Div(
                                'dither_num_columns',
                                css_class='col'
                            ),
                            css_class='form-row'
                        ),
                        Div(
                            Div(
                                'dither_orientation',
                                css_class='col'
                            ),
                            Div(
                                'dither_center',
                                css_class='col'
                            ),
                            css_class='form-row'
                        ),
                        css_id=f'{form_name}_dithering'
                        ),
                    Tab('Mosaicing',
                        Alert(
                            content="Mosaicing will only be applied if you have a single Configuration specified.",
                            css_class='alert-warning'
                        ),
                        Div(
                            Div(
                                'mosaic_pattern',
                                css_class='col'
                            ),
                            Div(
                                'mosaic_num_points',
                                css_class='col'
                            ),
                            css_class='form-row'
                        ),
                        Div(
                            Div(
                                'mosaic_point_overlap',
                                css_class='col'
                            ),
                            Div(
                                'mosaic_line_overlap',
                                css_class='col'
                            ),
                            css_class='form-row'
                        ),
                        Div(
                            Div(
                                'mosaic_num_rows',
                                css_class='col'
                            ),
                            Div(
                                'mosaic_num_columns',
                                css_class='col'
                            ),
                            css_class='form-row'
                        ),
                        Div(
                            Div(
                                'mosaic_orientation',
                                css_class='col'
                            ),
                            Div(
                                'mosaic_center',
                                css_class='col'
                            ),
                            css_class='form-row'
                        ),
                        css_id=f'{form_name}_mosaicing'
                        )
                ),
                active=False,
                css_id=f'{form_name}-expansions-group'
            )
        )


class ConfigurationLayout(Layout):
    def __init__(self, form_name, instrument_config_layout_class, oe_groups, *args, **kwargs):
        self.form_name = form_name
        self.instrument_config_layout_class = instrument_config_layout_class
        super().__init__(
            Div(
                HTML('''<br/><h2>Configurations:</h2>''')
            ),
            TabHolder(
                *self._get_config_tabs(oe_groups, MAX_CONFIGURATIONS)
            )
        )

    def _get_config_tabs(self, oe_groups, num_tabs):
        tabs = []
        for i in range(num_tabs):
            tabs.append(
                Tab(f'{i+1}',
                    *self._get_config_layout(i+1, oe_groups),
                    css_id=f'{self.form_name}_config_{i+1}'
                    ),
            )
        return tuple(tabs)

    def _get_config_layout(self, instance, oe_groups):
        return (
            Alert(
                content="""When using multiple configurations, ensure the instrument types are all
                            available on the same telescope class.
                        """,
                css_class='alert-warning'
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
            Div(
                Div(
                    f'c_{instance}_repeat_duration',
                    css_class='col'
                ),
                css_class='form-row'
            ),
            *self._get_target_override(instance),
            Accordion(
                AccordionGroup('Instrument Configurations',
                               self.instrument_config_layout_class(self.form_name, instance, oe_groups),
                               css_id=f'{self.form_name}-c-{instance}-instrument-configs'
                               ),
                AccordionGroup('Constraints',
                               Div(
                                   Div(
                                       f'c_{instance}_max_airmass',
                                       css_class='col'
                                   ),
                                   css_class='form-row'
                               ),
                               Div(
                                   Div(
                                       f'c_{instance}_min_lunar_distance',
                                       css_class='col'
                                   ),
                                   Div(
                                       f'c_{instance}_max_lunar_phase',
                                       css_class='col'
                                   ),
                                   css_class='form-row'
                               ),
                               ),
                AccordionGroup('Fractional Ephemeris Rate',
                               Div(
                                   HTML(f'''<br/><p>{fractional_ephemeris_rate_help}</p>''')
                               ),
                               Div(
                                   f'c_{instance}_fractional_ephemeris_rate',
                                   css_class='form-col'
                               )
                               ),
            )
        )

    def _get_target_override(self, instance):
        if instance == 1:
            return ()
        else:
            return (
                Div(
                    f'c_{instance}_target_override',
                    css_class='form-row'
                )
            )


class MuscatConfigurationLayout(ConfigurationLayout):
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


class SpectralConfigurationLayout(ConfigurationLayout):
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


class InstrumentConfigLayout(Layout):
    def __init__(self, form_name, config_instance, oe_groups, *args, **kwargs):
        self.form_name = form_name
        super().__init__(
            TabHolder(
                *self._get_ic_tabs(config_instance, oe_groups, MAX_INSTRUMENT_CONFIGS)
            )
        )

    def _get_ic_tabs(self, config_instance, oe_groups, num_tabs):
        tabs = []
        for i in range(num_tabs):
            tabs.append(
                Tab(f'{i+1}',
                    *self._get_ic_layout(config_instance, i+1, oe_groups),
                    css_id=f'{self.form_name}_c_{config_instance}_ic_{i+1}'
                    ),
            )
        return tuple(tabs)

    def _get_oe_groups_layout(self, config_instance, instance, oe_groups):
        oe_groups_layout = []
        for oe_group1, oe_group2 in zip(*[iter(oe_groups)]*2):
            oe_groups_layout.append(
                Div(
                    Div(
                        f'c_{config_instance}_ic_{instance}_{oe_group1}',
                        css_class='col'
                    ),
                    Div(
                        f'c_{config_instance}_ic_{instance}_{oe_group2}',
                        css_class='col'
                    ),
                    css_class='form-row'
                )
            )
        if len(oe_groups) % 2 == 1:
            # We have one excess oe_group, so add it here
            oe_groups_layout.append(
                Div(
                    Div(
                        f'c_{config_instance}_ic_{instance}_{oe_groups[-1]}',
                        css_class='col'
                    ),
                    css_class='form-row'
                )
            )
        return oe_groups_layout

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
            *self._get_oe_groups_layout(config_instance, instance, oe_groups)
        )


class MuscatInstrumentConfigLayout(InstrumentConfigLayout):
    def __init__(self, form_name, config_instance, oe_groups, *args, **kwargs):
        super().__init__(form_name, config_instance, oe_groups, *args, **kwargs)

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


class SpectralInstrumentConfigLayout(InstrumentConfigLayout):
    def __init__(self, form_name, config_instance, oe_groups, *args, **kwargs):
        super().__init__(form_name, config_instance, oe_groups, *args, **kwargs)

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


class LCOBaseObservationForm(BaseRoboticObservationForm, LCOBaseForm):
    """
    The LCOBaseObservationForm provides the base set of utilities to construct an observation at Las Cumbres
    Observatory. It must be subclassed to be used, as some methods are not implemented in this class.
    """
    name = forms.CharField()
    ipp_value = forms.FloatField(label='Intra Proposal Priority (IPP factor)',
                                 min_value=0.5,
                                 max_value=2,
                                 initial=1.05,
                                 help_text=ipp_value_help)
    start = forms.CharField(widget=forms.TextInput(attrs={'type': 'date'}))
    end = forms.CharField(widget=forms.TextInput(attrs={'type': 'date'}),
                          help_text=end_help)
    observation_mode = forms.ChoiceField(
        choices=(('NORMAL', 'Normal'), ('RAPID_RESPONSE', 'Rapid-Response'), ('TIME_CRITICAL', 'Time-Critical')),
        help_text=observation_mode_help
    )
    optimization_type = forms.ChoiceField(
        choices=(('TIME', 'Time'), ('AIRMASS', 'Airmass')),
        required=False,
        help_text=optimization_type_help
    )
    configuration_repeats = forms.IntegerField(
        min_value=1,
        initial=1,
        required=False,
        label='Configuration Repeats',
        help_text='Number of times to repeat the set of configurations, usually used for nodding between 2+ targets'
    )
    period = forms.FloatField(help_text='Decimal Hours', required=False, min_value=0.0)
    jitter = forms.FloatField(help_text='Decimal Hours', required=False, min_value=0.0)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['proposal'] = forms.ChoiceField(choices=self.proposal_choices())
        self.helper.layout = Layout(
            self.common_layout,
            self.layout(),
            self.button_layout()
        )

    def button_layout(self):
        target_id = self.initial.get('target_id')
        return ButtonHolder(
            Submit('submit', 'Submit'),
            Submit('validateButton', 'Validate'),
            HTML(f'''<a class="btn btn-outline-primary" href={{% url 'tom_targets:detail' {target_id} %}}>
                         Back</a>''')
        )

    def clean_start(self):
        start = self.cleaned_data['start']
        return parse(start).isoformat()

    def clean_end(self):
        end = self.cleaned_data['end']
        return parse(end).isoformat()

    def validate_at_facility(self):
        obs_module = get_service_class(self.cleaned_data['facility'])
        response = obs_module().validate_observation(self.observation_payload())
        if response.get('request_durations', {}).get('duration'):
            duration = response['request_durations']['duration']
            self.validation_message = f"This observation is valid with a duration of {duration} seconds."
        if response.get('errors'):
            self.add_error(None, self._flatten_error_dict(response['errors']))

    def is_valid(self):
        super().is_valid()
        self.validate_at_facility()
        if self._errors:
            logger.warn(f'Facility submission has errors {self._errors}')
        return not self._errors

    def _flatten_error_dict(self, error_dict):
        non_field_errors = []
        for k, v in error_dict.items():
            if isinstance(v, list):
                for i in v:
                    if isinstance(i, str):
                        if k in self.fields:
                            self.add_error(k, i)
                        else:
                            non_field_errors.append('{}: {}'.format(k, i))
                    if isinstance(i, dict):
                        non_field_errors.append(self._flatten_error_dict(i))
            elif isinstance(v, str):
                if k in self.fields:
                    self.add_error(k, v)
                else:
                    non_field_errors.append('{}: {}'.format(k, v))
            elif isinstance(v, dict):
                non_field_errors.append(self._flatten_error_dict(v))

        return non_field_errors

    def _build_target_extra_params(self, configuration_id=1):
        # if a fractional_ephemeris_rate has been specified, add it as an extra_param
        # to the target_fields
        if 'fractional_ephemeris_rate' in self.cleaned_data:
            return {'fractional_ephemeris_rate': self.cleaned_data['fractional_ephemeris_rate']}
        return {}

    def _build_target_fields(self, target_id, configuration_id=1):
        target = Target.objects.get(pk=target_id)
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
                'epoch_of_elements': 'epochofel',
                'epoch_of_perihelion': 'epochofperih',
            }
            # The fields to include in the payload depend on the scheme. Add
            # only those that are required
            fields = (REQUIRED_NON_SIDEREAL_FIELDS
                      + REQUIRED_NON_SIDEREAL_FIELDS_PER_SCHEME[target.scheme])
            for field in fields:
                lco_field = field_mapping.get(field, field)
                target_fields[lco_field] = getattr(target, field)

            #
            # Handle extra_params
            #
            if 'extra_params' not in target_fields:
                target_fields['extra_params'] = {}
            target_fields['extra_params'].update(self._build_target_extra_params(configuration_id))

        return target_fields

    def _build_acquisition_config(self, configuration_id=1):
        acquisition_config = {}

        return acquisition_config

    def _build_guiding_config(self, configuration_id=1):
        guiding_config = {}

        return guiding_config

    def _build_instrument_config(self):
        return []

    def _build_configuration(self):
        configuration = {
            'type': self.instrument_to_type(self.cleaned_data['instrument_type']),
            'instrument_type': self.cleaned_data['instrument_type'],
            'target': self._build_target_fields(self.cleaned_data['target_id']),
            'instrument_configs': self._build_instrument_config(),
            'acquisition_config': self._build_acquisition_config(),
            'guiding_config': self._build_guiding_config(),
            'constraints': {
                'max_airmass': self.cleaned_data['max_airmass'],
            }
        }

        if 'min_lunar_distance' in self.cleaned_data and self.cleaned_data.get('min_lunar_distance') is not None:
            configuration['constraints']['min_lunar_distance'] = self.cleaned_data['min_lunar_distance']

        return configuration

    def _build_location(self):
        return {'telescope_class': self._get_instruments()[self.cleaned_data['instrument_type']]['class']}

    def _expand_cadence_request(self, payload):
        payload['requests'][0]['cadence'] = {
            'start': self.cleaned_data['start'],
            'end': self.cleaned_data['end'],
            'period': self.cleaned_data['period'],
            'jitter': self.cleaned_data['jitter']
        }
        payload['requests'][0]['windows'] = []

        # use the LCO Observation Portal candence builder to build the candence
        response = make_request(
            'POST',
            PORTAL_URL + '/api/requestgroups/cadence/',
            json=payload,
            headers={'Authorization': 'Token {0}'.format(LCO_SETTINGS['api_key'])}
        )
        return response.json()

    def observation_payload(self):
        payload = {
            'name': self.cleaned_data['name'],
            'proposal': self.cleaned_data['proposal'],
            'ipp_value': self.cleaned_data['ipp_value'],
            'operator': 'SINGLE',
            'observation_type': self.cleaned_data['observation_mode'],
            'requests': [
                {
                    'configurations': [self._build_configuration()],
                    'windows': [
                        {
                            'start': self.cleaned_data['start'],
                            'end': self.cleaned_data['end']
                        }
                    ],
                    'location': self._build_location()
                }
            ]
        }
        if self.cleaned_data.get('period') and self.cleaned_data.get('jitter') is not None:
            payload = self._expand_cadence_request(payload)

        return payload


class LCOOldStyleObservationForm(LCOBaseObservationForm):
    """
    The LCOOldStyleObservationForm provides the backwards compatibility for the Imaging and Spectral Sequence
    forms to remain the same as they were previously despite the upgrades to the other LCO forms.
    """
    exposure_count = forms.IntegerField(min_value=1)
    exposure_time = forms.FloatField(min_value=0.1,
                                     widget=forms.TextInput(attrs={'placeholder': 'Seconds'}),
                                     help_text=exposure_time_help)
    max_airmass = forms.FloatField(help_text=max_airmass_help, min_value=0)
    min_lunar_distance = forms.IntegerField(min_value=0, label='Minimum Lunar Distance', required=False)
    max_lunar_phase = forms.FloatField(help_text=max_lunar_phase_help, min_value=0,
                                       max_value=1.0, label='Maximum Lunar Phase', required=False)
    fractional_ephemeris_rate = forms.FloatField(min_value=0.0, max_value=1.0,
                                                 label='Fractional Ephemeris Rate',
                                                 help_text='Value between 0 (Sidereal Tracking) '
                                                           'and 1 (Target Tracking). If blank, Target Tracking.',
                                                 required=False)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['filter'] = forms.ChoiceField(choices=self.filter_choices())
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

    def _build_instrument_config(self):
        instrument_config = {
            'exposure_count': self.cleaned_data['exposure_count'],
            'exposure_time': self.cleaned_data['exposure_time'],
            'optical_elements': {
                'filter': self.cleaned_data['filter']
            }
        }

        return [instrument_config]


class LCOFullObservationForm(LCOBaseObservationForm):
    """
    The LCOFullObservationForm has all capabilities to construct an observation at Las Cumbres
    Observatory. While the forms that inherit from it provide a subset of instruments and filters, the
    LCOFullObservationForm presents the user with all of the instrument and filter options that the facility has to
    offer.
    """
    dither_pattern = forms.ChoiceField(
        choices=(('', 'None'), ('line', 'Line'), ('grid', 'Grid'), ('spiral', 'Spiral')),
        required=False,
        help_text='Expand your Instrument Configurations with a set of offsets from the target following a pattern.'
    )
    dither_num_points = forms.IntegerField(min_value=2, label='Number of Points',
                                           help_text='Number of Points in the pattern (Line and Spiral only).',
                                           required=False)
    dither_point_spacing = forms.FloatField(
        label='Point Spacing', help_text='Vertical spacing between offsets.', required=False, min_value=0.0)
    dither_line_spacing = forms.FloatField(
        label='Line Spacing', help_text='Horizontal spacing between offsets (Grid only).',
        required=False, min_value=0.0)
    dither_orientation = forms.FloatField(
        label='Orientation',
        help_text='Angular rotation of the pattern in degrees, measured clockwise East of North (Line and Grid only).',
        required=False, min_value=0.0)
    dither_num_rows = forms.IntegerField(
        min_value=1, label='Number of Rows', required=False,
        help_text='Number of offsets in the pattern in the RA direction (Grid only).')
    dither_num_columns = forms.IntegerField(
        min_value=1, label='Number of Columns', required=False,
        help_text='Number of offsets in the pattern in the declination direction (Grid only).')
    dither_center = forms.ChoiceField(
        choices=((True, 'True'), (False, 'False')),
        label='Center',
        required=False,
        help_text='If True, pattern is centered on initial target. Otherwise pattern begins at initial target.'
    )
    mosaic_pattern = forms.ChoiceField(
        choices=(('', 'None'), ('line', 'Line'), ('grid', 'Grid')),
        required=False,
        help_text="""Expand your Configurations with a set of different targets following a mosaic pattern.
                     Only works with Sidereal targets.
                  """
    )
    mosaic_num_points = forms.IntegerField(min_value=2, label='Number of Points',
                                           help_text='Number of Points in the pattern (Line only).', required=False)
    mosaic_point_overlap = forms.FloatField(
        label='Point Overlap Percent',
        help_text='Percentage overlap of pointings in the pattern as a percent of declination in FOV.',
        required=False, min_value=0.0, max_value=100.0)
    mosaic_line_overlap = forms.FloatField(
        label='Line Overlap Percent',
        help_text='Percentage overlap of pointings in the pattern as a percent of RA in FOV (Grid only).',
        required=False, min_value=0.0, max_value=100.0)
    mosaic_orientation = forms.FloatField(
        label='Orientation',
        help_text='Angular rotation of the pattern in degrees, measured clockwise East of North.',
        required=False, min_value=0.0)
    mosaic_num_rows = forms.IntegerField(
        min_value=1, label='Number of Rows',
        help_text='Number of pointings in the pattern in the declination direction (Grid only).', required=False)
    mosaic_num_columns = forms.IntegerField(
        min_value=1, label='Number of Columns',
        help_text='Number of pointings in the pattern in the RA direction (Grid only).', required=False)
    mosaic_center = forms.ChoiceField(
        choices=((True, 'True'), (False, 'False')),
        label='Center',
        required=False,
        help_text='If True, pattern is centered on initial target. Otherwise pattern begins at initial target.'
    )

    def __init__(self, data=None, **kwargs):
        # convert data argument field names to the proper fields. Data is assumed to be observation payload format
        data = self.convert_old_observation_payload_to_fields(data)
        super().__init__(data, **kwargs)
        for j in range(MAX_CONFIGURATIONS):
            self.fields[f'c_{j+1}_instrument_type'] = forms.ChoiceField(
                choices=self.instrument_choices(), required=False, help_text=instrument_type_help,
                label='Instrument Type')
            self.fields[f'c_{j+1}_configuration_type'] = forms.ChoiceField(
                choices=self.configuration_type_choices(), required=False, label='Configuration Type')
            self.fields[f'c_{j+1}_repeat_duration'] = forms.FloatField(
                help_text=repeat_duration_help, required=False, label='Repeat Duration',
                widget=forms.TextInput(attrs={'placeholder': 'Seconds'}))
            self.fields[f'c_{j+1}_max_airmass'] = forms.FloatField(
                help_text=max_airmass_help, label='Max Airmass', min_value=0, initial=1.6, required=False)
            self.fields[f'c_{j+1}_min_lunar_distance'] = forms.IntegerField(
                min_value=0, label='Minimum Lunar Distance', required=False)
            self.fields[f'c_{j+1}_max_lunar_phase'] = forms.FloatField(
                help_text=max_lunar_phase_help, min_value=0, max_value=1.0, label='Maximum Lunar Phase', required=False)
            self.fields[f'c_{j+1}_fractional_ephemeris_rate'] = forms.FloatField(
                min_value=0.0, max_value=1.0, label='Fractional Ephemeris Rate',
                help_text='Value between 0 (Sidereal Tracking) '
                'and 1 (Target Tracking). If blank, Target Tracking.',
                required=False
            )
            self.fields[f'c_{j+1}_target_override'] = forms.ChoiceField(
                choices=self.target_group_choices(),
                required=False,
                help_text='Set a different target for this configuration. Must be in the same target group.',
                label='Substitute Target for this Configuration'
            )
            for i in range(MAX_INSTRUMENT_CONFIGS):
                self.fields[f'c_{j+1}_ic_{i+1}_exposure_count'] = forms.IntegerField(
                    min_value=1, label='Exposure Count', initial=1, required=False)
                self.fields[f'c_{j+1}_ic_{i+1}_exposure_time'] = forms.FloatField(
                    min_value=0.1, label='Exposure Time',
                    widget=forms.TextInput(attrs={'placeholder': 'Seconds'}),
                    help_text=exposure_time_help, required=False)
                for oe_group in self.get_optical_element_groups():
                    oe_group_plural = oe_group + 's'
                    self.fields[f'c_{j+1}_ic_{i+1}_{oe_group}'] = forms.ChoiceField(
                        choices=self.filter_choices_for_group(oe_group_plural), required=False,
                        label=oe_group.replace('_', ' ').capitalize())
        self.helper.layout = Layout(
            self.common_layout,
            self.layout(),
            self.button_layout()
        )
        if isinstance(self, CadenceForm):
            self.helper.layout.insert(2, self.cadence_layout())

    def convert_old_observation_payload_to_fields(self, data):
        """ This is a backwards compatibility function to allow us to load old-format observation parameters
            for existing ObservationRecords, which use the old form, but may still need to use the new form
            to submit cadence strategy observations.
        """
        if not data:
            return None
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

    def form_name(self):
        return 'base'

    def instrument_config_layout_class(self):
        return InstrumentConfigLayout

    def configuration_layout_class(self):
        return ConfigurationLayout

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
            self.configuration_layout_class()(
                self.form_name(), self.instrument_config_layout_class(), self.get_optical_element_groups()
            ),
            AdvancedExpansionsLayout(self.form_name())
        )

    def _build_target_extra_params(self, configuration_id=1):
        # if a fractional_ephemeris_rate has been specified, add it as an extra_param
        # to the target_fields
        if f'c_{configuration_id}_fractional_ephemeris_rate' in self.cleaned_data:
            return {'fractional_ephemeris_rate': self.cleaned_data[f'c_{configuration_id}_fractional_ephemeris_rate']}
        return {}

    def _build_instrument_config(self, instrument_type, configuration_id, id):
        # If the instrument config did not have an exposure time set, leave it out by returning None
        if not self.cleaned_data.get(f'c_{configuration_id}_ic_{id}_exposure_time'):
            return None
        instrument_config = {
            'exposure_count': self.cleaned_data[f'c_{configuration_id}_ic_{id}_exposure_count'],
            'exposure_time': self.cleaned_data[f'c_{configuration_id}_ic_{id}_exposure_time'],
            'optical_elements': {}
        }
        for oe_group in self.get_optical_element_groups():
            instrument_config['optical_elements'][oe_group] = self.cleaned_data.get(
                f'c_{configuration_id}_ic_{id}_{oe_group}')

        return instrument_config

    def _build_instrument_configs(self, instrument_type, configuration_id):
        ics = []
        for i in range(MAX_INSTRUMENT_CONFIGS):
            ic = self._build_instrument_config(instrument_type, configuration_id, i+1)
            # This will only include instrument configs with an exposure time set
            if ic:
                ics.append(ic)

        return ics

    def _build_configuration(self, id):
        instrument_configs = self._build_instrument_configs(self.cleaned_data[f'c_{id}_instrument_type'], id)
        # Check if the instrument configs are empty, and if so, leave this configuration out by returning None
        if not instrument_configs:
            return None
        configuration = {
            'type': self.cleaned_data[f'c_{id}_configuration_type'],
            'instrument_type': self.cleaned_data[f'c_{id}_instrument_type'],
            'instrument_configs': instrument_configs,
            'acquisition_config': self._build_acquisition_config(id),
            'guiding_config': self._build_guiding_config(id),
            'constraints': {
                'max_airmass': self.cleaned_data[f'c_{id}_max_airmass'],
            }
        }
        if self.cleaned_data.get(f'c_{id}_target_override'):
            configuration['target'] = self._build_target_fields(self.cleaned_data[f'c_{id}_target_override'])
        else:
            configuration['target'] = self._build_target_fields(self.cleaned_data['target_id'])
        if self.cleaned_data.get(f'c_{id}_repeat_duration'):
            configuration['repeat_duration'] = self.cleaned_data[f'c_{id}_repeat_duration']
        if self.cleaned_data.get(f'c_{id}_min_lunar_distance'):
            configuration['constraints']['min_lunar_distance'] = self.cleaned_data[f'c_{id}_min_lunar_distance']
        if self.cleaned_data.get(f'c_{id}_max_lunar_phase'):
            configuration['constraints']['max_lunar_phase'] = self.cleaned_data[f'c_{id}_max_lunar_phase']

        return configuration

    def _build_configurations(self):
        configurations = []
        for j in range(MAX_CONFIGURATIONS):
            configuration = self._build_configuration(j+1)
            if configuration:
                configurations.append(configuration)

        return configurations

    def _expand_dither_pattern(self, configuration):
        payload = {
            'configuration': configuration,
            'pattern': self.cleaned_data.get('dither_pattern'),
            'center': self.cleaned_data.get('dither_center')
        }
        if self.cleaned_data.get('dither_orientation'):
            payload['orientation'] = self.cleaned_data['dither_orientation']
        if self.cleaned_data.get('dither_point_spacing'):
            payload['point_spacing'] = self.cleaned_data['dither_point_spacing']
        if payload['pattern'] in ['line', 'spiral'] and self.cleaned_data.get('dither_num_points'):
            payload['num_points'] = self.cleaned_data['dither_num_points']
        if payload['pattern'] == 'grid':
            if self.cleaned_data.get('dither_num_rows'):
                payload['num_rows'] = self.cleaned_data['dither_num_rows']
            if self.cleaned_data.get('dither_num_columns'):
                payload['num_columns'] = self.cleaned_data['dither_num_columns']
            if self.cleaned_data.get('dither_line_spacing'):
                payload['line_spacing'] = self.cleaned_data['dither_line_spacing']
        # Use the LCO Observation Portal dither pattern expansion to expand the configuration
        response_json = {}
        try:
            response = make_request(
                'POST',
                PORTAL_URL + '/api/configurations/dither/',
                json=payload,
                headers={'Authorization': 'Token {0}'.format(LCO_SETTINGS['api_key'])}
            )
            response_json = response.json()
            response.raise_for_status()
            return response_json
        except Exception:
            logger.warning(f"Error expanding dither pattern: {response_json}")
            return configuration

    def _expand_mosaic_pattern(self, request):
        payload = {
            'request': request,
            'pattern': self.cleaned_data.get('mosaic_pattern'),
            'center': self.cleaned_data.get('mosaic_center')
        }
        if self.cleaned_data.get('mosaic_orientation'):
            payload['orientation'] = self.cleaned_data['mosaic_orientation']
        if self.cleaned_data.get('mosaic_point_overlap'):
            payload['point_overlap_percent'] = self.cleaned_data['mosaic_point_overlap']
        if payload['pattern'] == 'line' and self.cleaned_data.get('mosaic_num_points'):
            payload['num_points'] = self.cleaned_data['mosaic_num_points']
        if payload['pattern'] == 'grid':
            if self.cleaned_data.get('mosaic_num_rows'):
                payload['num_rows'] = self.cleaned_data['mosaic_num_rows']
            if self.cleaned_data.get('mosaic_num_columns'):
                payload['num_columns'] = self.cleaned_data['mosaic_num_columns']
            if self.cleaned_data.get('mosaic_line_overlap'):
                payload['line_overlap_percent'] = self.cleaned_data['mosaic_line_overlap']

        # Use the LCO Observation Portal dither pattern expansion to expand the configuration
        response_json = {}
        try:
            response = make_request(
                'POST',
                PORTAL_URL + '/api/requests/mosaic/',
                json=payload,
                headers={'Authorization': 'Token {0}'.format(LCO_SETTINGS['api_key'])}
            )
            response_json = response.json()
            response.raise_for_status()
            return response_json
        except Exception:
            logger.warning(f"Error expanding mosaic pattern: {response_json}")
            return request

    def _build_location(self, configuration_id=1):
        return {
            'telescope_class': self._get_instruments()[
                self.cleaned_data[f'c_{configuration_id}_instrument_type']]['class']
        }

    def observation_payload(self):
        payload = {
            'name': self.cleaned_data['name'],
            'proposal': self.cleaned_data['proposal'],
            'ipp_value': self.cleaned_data['ipp_value'],
            'operator': 'SINGLE',
            'observation_type': self.cleaned_data['observation_mode'],
            'requests': [
                {
                    'optimization_type': self.cleaned_data['optimization_type'],
                    'configuration_repeats': self.cleaned_data['configuration_repeats'],
                    'configurations': self._build_configurations(),
                    'windows': [
                        {
                            'start': self.cleaned_data['start'],
                            'end': self.cleaned_data['end']
                        }
                    ],
                    'location': self._build_location()
                }
            ]
        }
        if (self.cleaned_data.get('dither_pattern') and self.cleaned_data.get('dither_point_spacing') and len(
                payload['requests'][0]['configurations']) == 1):
            payload['requests'][0]['configurations'][0] = self._expand_dither_pattern(
                payload['requests'][0]['configurations'][0])
        if self.cleaned_data.get('mosaic_pattern') and len(payload['requests'][0]['configurations']) == 1:
            payload['requests'][0] = self._expand_mosaic_pattern(payload['requests'][0])
        if self.cleaned_data.get('period') and self.cleaned_data.get('jitter') is not None:
            payload = self._expand_cadence_request(payload)

        return payload


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
        super().__init__(*args, **kwargs)
        # Need to add the muscat specific exposure time fields to this form
        for j in range(MAX_CONFIGURATIONS):
            self.fields[f'c_{j+1}_guide_mode'] = forms.ChoiceField(
                choices=self.mode_choices('guiding'), required=False, label='Guide Mode')
            for i in range(MAX_INSTRUMENT_CONFIGS):
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
                    help_text=muscat_exposure_mode_help
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

    def _build_guiding_config(self, configuration_id):
        guiding_config = super()._build_guiding_config()
        guiding_config['mode'] = self.cleaned_data[f'c_{configuration_id}_guide_mode']
        # Muscat guiding `optional` setting only makes sense set to true from the telescope software perspective
        guiding_config['optional'] = True
        return guiding_config

    def _build_instrument_config(self, instrument_type, configuration_id, id):
        # Refer to the 'MUSCAT instrument configuration' section on this page: https://developers.lco.global/
        if not (self.cleaned_data.get(f'c_{configuration_id}_ic_{id}_exposure_time_g') and self.cleaned_data.get(
            f'c_{configuration_id}_ic_{id}_exposure_time_r') and self.cleaned_data.get(
                f'c_{configuration_id}_ic_{id}_exposure_time_i') and self.cleaned_data.get(
                    f'c_{configuration_id}_ic_{id}_exposure_time_z')):
            return None
        instrument_config = {
            'exposure_count': self.cleaned_data[f'c_{configuration_id}_ic_{id}_exposure_count'],
            'exposure_time': max(
                self.cleaned_data[f'c_{configuration_id}_ic_{id}_exposure_time_g'],
                self.cleaned_data[f'c_{configuration_id}_ic_{id}_exposure_time_r'],
                self.cleaned_data[f'c_{configuration_id}_ic_{id}_exposure_time_i'],
                self.cleaned_data[f'c_{configuration_id}_ic_{id}_exposure_time_z']
            ),
            'optical_elements': {},
            'mode': self.cleaned_data[f'c_{configuration_id}_ic_{id}_readout_mode'],
            'extra_params': {
                'exposure_mode': self.cleaned_data[f'c_{configuration_id}_ic_{id}_exposure_mode'],
                'exposure_time_g': self.cleaned_data[f'c_{configuration_id}_ic_{id}_exposure_time_g'],
                'exposure_time_r': self.cleaned_data[f'c_{configuration_id}_ic_{id}_exposure_time_r'],
                'exposure_time_i': self.cleaned_data[f'c_{configuration_id}_ic_{id}_exposure_time_i'],
                'exposure_time_z': self.cleaned_data[f'c_{configuration_id}_ic_{id}_exposure_time_z'],
            }
        }
        for oe_group in self.get_optical_element_groups():
            instrument_config['optical_elements'][oe_group] = self.cleaned_data.get(
                f'c_{configuration_id}_ic_{id}_{oe_group}')

        return instrument_config


class LCOSpectroscopyObservationForm(LCOFullObservationForm):
    """
    The LCOSpectroscopyObservationForm allows the selection of parameters for observing using LCO's Spectrographs. The
    list of spectrographs and their details can be found here: https://lco.global/observatory/instruments/
    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for j in range(MAX_CONFIGURATIONS):
            self.fields[f'c_{j+1}_acquisition_mode'] = forms.ChoiceField(
                choices=self.mode_choices('acquisition', use_code_only=True), required=False, label='Acquisition Mode')
            for i in range(MAX_INSTRUMENT_CONFIGS):
                self.fields[f'c_{j+1}_ic_{i+1}_rotator_mode'] = forms.ChoiceField(
                    choices=self.mode_choices('rotator'), label='Rotator Mode', required=False,
                    help_text='Only for Floyds')
                self.fields[f'c_{j+1}_ic_{i+1}_rotator_angle'] = forms.FloatField(
                    min_value=0.0, initial=0.0,
                    help_text='Rotation angle of slit. Only for Floyds `Slit Position Angle` rotator mode',
                    label='Rotator Angle', required=False
                )
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

    def _build_acquisition_config(self, configuration_id):
        acquisition_config = {'mode': self.cleaned_data[f'c_{configuration_id}_acquisition_mode']}

        return acquisition_config

    def _build_configuration(self, id):
        configuration = super()._build_configuration(id)
        if not configuration:
            return None
        # If NRES, adjust the configuration types to match nres types
        if 'NRES' in configuration['instrument_type'].upper():
            if configuration['type'] == 'SPECTRUM':
                configuration['type'] = 'NRES_SPECTRUM'
            elif configuration['type'] == 'REPEAT_SPECTRUM':
                configuration['type'] = 'REPEAT_NRES_SPECTRUM'

        return configuration

    def _build_instrument_config(self, instrument_type, configuration_id, id):
        instrument_config = super()._build_instrument_config(instrument_type, configuration_id, id)
        if not instrument_config:
            return None
        # If floyds, add the rotator mode and angle in
        if 'FLOYDS' in instrument_type.upper() or 'SOAR' in instrument_type.upper():
            instrument_config['rotator_mode'] = self.cleaned_data[f'c_{configuration_id}_ic_{id}_rotator_mode']
            if instrument_config['rotator_mode'] == 'SKY':
                instrument_config['extra_params'] = {'rotator_angle': self.cleaned_data.get(
                    f'c_{configuration_id}_ic_{id}_rotator_angle', 0)}
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
    valid_filters = ['U', 'B', 'V', 'R', 'I', 'up', 'gp', 'rp', 'ip', 'zs', 'w']
    cadence_frequency = forms.IntegerField(required=True, help_text='in hours')

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        # Add fields for each available filter as specified in the filters property
        for filter_code, filter_name in LCOPhotometricSequenceForm.filter_choices():
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

    def _build_instrument_config(self):
        """
        Because the photometric sequence form provides form inputs for 10 different filters, they must be
        constructed into a list of instrument configurations as per the LCO API. This method constructs the
        instrument configurations in the appropriate manner.
        """
        instrument_config = []
        for filter_name in self.valid_filters:
            if len(self.cleaned_data[filter_name]) > 0:
                instrument_config.append({
                    'exposure_count': self.cleaned_data[filter_name][1],
                    'exposure_time': self.cleaned_data[filter_name][0],
                    'optical_elements': {
                        'filter': filter_name
                    }
                })

        return instrument_config

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

    @staticmethod
    def instrument_choices():
        """
        This method returns only the instrument choices available in the current SNEx photometric sequence form.
        """
        return sorted([(k, v['name'])
                       for k, v in LCOPhotometricSequenceForm._get_instruments().items()
                       if k in LCOPhotometricSequenceForm.valid_instruments],
                      key=lambda inst: inst[1])

    @staticmethod
    def filter_choices():
        return sorted(set([
            (f['code'], f['name']) for ins in LCOPhotometricSequenceForm._get_instruments().values() for f in
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
        for filter_name in self.valid_filters:
            filter_layout.append(Row(MultiWidgetField(filter_name, attrs={'min': 0})))

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

    def _build_instrument_config(self):
        instrument_configs = super()._build_instrument_config()
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

    @staticmethod
    def instrument_choices():
        # SNEx only uses the Spectroscopic Sequence Form with FLOYDS
        # This doesn't need to be sorted because it will only return one instrument
        return [(k, v['name'])
                for k, v in LCOSpectroscopicSequenceForm._get_instruments().items()
                if k == '2M0-FLOYDS-SCICAM']

    @staticmethod
    def filter_choices():
        # SNEx only uses the Spectroscopic Sequence Form with FLOYDS
        return sorted(set([
            (f['code'], f['name']) for name, ins in LCOSpectroscopicSequenceForm._get_instruments().items() for f in
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


class LCOObservationTemplateForm(GenericTemplateForm, LCOTemplateBaseForm):
    """
    The template form modifies the LCOTemplateBaseForm in order to only provide fields
    that make sense to stay the same for the template. For example, there is no
    point to making start_time an available field, as it will change between
    observations.
    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field_name in ['groups', 'target_id']:
            self.fields.pop(field_name, None)
        for field in self.fields:
            if field != 'template_name':
                self.fields[field].required = False
        self.helper.layout = Layout(
            self.common_layout,
            Div(
                Div(
                    'proposal', 'ipp_value', 'filter', 'instrument_type',
                    css_class='col'
                ),
                Div(
                    'exposure_count', 'exposure_time', 'max_airmass',
                    css_class='col'
                ),
                css_class='form-row',
            )
        )


class LCOFacility(BaseRoboticObservationFacility):
    """
    The ``LCOFacility`` is the interface to the Las Cumbres Observatory Observation Portal. For information regarding
    LCO observing and the available parameters, please see https://observe.lco.global/help/.
    """

    name = 'LCO'
    # TODO: make the keys the display values instead
    observation_forms = {
        'IMAGING': LCOImagingObservationForm,
        'MUSCAT_IMAGING': LCOMuscatImagingObservationForm,
        'SPECTRA': LCOSpectroscopyObservationForm,
        'PHOTOMETRIC_SEQUENCE': LCOPhotometricSequenceForm,
        'SPECTROSCOPIC_SEQUENCE': LCOSpectroscopicSequenceForm
    }
    # The SITES dictionary is used to calculate visibility intervals in the
    # planning tool. All entries should contain latitude, longitude, elevation
    # and a code.
    # TODO: Flip sitecode and site name
    # TODO: Why is tlv not represented here?
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

    # TODO: this should be called get_form_class
    def get_form(self, observation_type):
        return self.observation_forms.get(observation_type, LCOOldStyleObservationForm)

    # TODO: this should be called get_template_form_class
    def get_template_form(self, observation_type):
        return LCOObservationTemplateForm

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
        return response.json()

    def cancel_observation(self, observation_id):
        requestgroup_id = self._get_requestgroup_id(observation_id)

        response = make_request(
            'POST',
            f'{PORTAL_URL}/api/requestgroups/{requestgroup_id}/cancel/',
            headers=self._portal_headers()
        )

        return response.json()['state'] == 'CANCELED'

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

    def get_start_end_keywords(self):
        return ('start', 'end')

    def get_terminal_observing_states(self):
        return TERMINAL_OBSERVING_STATES

    def get_failed_observing_states(self):
        return FAILED_OBSERVING_STATES

    def get_observing_sites(self):
        return self.SITES

    def get_facility_weather_urls(self):
        """
        `facility_weather_urls = {'code': 'XYZ', 'sites': [ site_dict, ... ]}`
        where
        `site_dict = {'code': 'XYZ', 'weather_url': 'http://path/to/weather'}`
        """
        # TODO: manually add a weather url for tlv
        facility_weather_urls = {
            'code': 'LCO',
            'sites': [
                {
                    'code': site['sitecode'],
                    'weather_url': f'https://weather.lco.global/#/{site["sitecode"]}'
                }
                for site in self.SITES.values()]
        }

        return facility_weather_urls

    def get_facility_status(self):
        """
        Get the telescope_states from the LCO API endpoint and simply
        transform the returned JSON into the following dictionary hierarchy
        for use by the facility_status.html template partial.

        facility_dict = {'code': 'LCO', 'sites': [ site_dict, ... ]}
        site_dict = {'code': 'XYZ', 'telescopes': [ telescope_dict, ... ]}
        telescope_dict = {'code': 'XYZ', 'status': 'AVAILABILITY'}

        Here's an example of the returned dictionary:

        literal_facility_status_example = {
            'code': 'LCO',
            'sites': [
                {
                    'code': 'BPL',
                    'telescopes': [
                        {
                            'code': 'bpl.doma.1m0a',
                            'status': 'AVAILABLE'
                        },
                    ],
                },
                {
                    'code': 'ELP',
                    'telescopes': [
                        {
                            'code': 'elp.doma.1m0a',
                            'status': 'AVAILABLE'
                        },
                        {
                            'code': 'elp.domb.1m0a',
                            'status': 'AVAILABLE'
                        },
                    ]
                }
            ]
        }

        :return: facility_dict
        """
        # make the request to the LCO API for the telescope_states
        response = make_request(
            'GET',
            PORTAL_URL + '/api/telescope_states/',
            headers=self._portal_headers()
        )
        telescope_states = response.json()

        # Now, transform the telescopes_state dictionary in a dictionary suitable
        # for the facility_status.html template partial.

        # set up the return value to be populated by the for loop below
        facility_status = {
            'code': self.name,
            'sites': []
        }
        site_list = [site["sitecode"] for site in self.SITES.values()]

        for telescope_key, telescope_value in telescope_states.items():
            [site_code, _, _] = telescope_key.split('.')

            # limit returned sites to those provided by the facility
            if site_code in site_list:

                # extract this telescope and it's status from the response
                telescope = {
                    'code': telescope_key,
                    'status': telescope_value[0]['event_type']
                }

                # get the site dictionary from the facilities list of sites
                # filter by site_code and provide a default (None) for new sites
                site = next((site_ix for site_ix in facility_status['sites']
                             if site_ix['code'] == site_code), None)
                # create the site if it's new and not yet in the facility_status['sites] list
                if site is None:
                    new_site = {
                        'code': site_code,
                        'telescopes': []
                    }
                    facility_status['sites'].append(new_site)
                    site = new_site

                # Now, add the telescope to the site's telescopes
                site['telescopes'].append(telescope)

        return facility_status

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

    def _get_requestgroup_id(self, observation_id):
        query_params = urlencode({'request_id': observation_id})

        response = make_request(
            'GET',
            f'{PORTAL_URL}/api/requestgroups?{query_params}',
            headers=self._portal_headers()
        )
        requestgroups = response.json()

        if requestgroups['count'] == 1:
            return requestgroups['results'][0]['id']

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
