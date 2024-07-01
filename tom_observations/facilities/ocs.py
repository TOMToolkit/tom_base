from datetime import datetime
import logging
import requests
from urllib.parse import urlencode, urljoin

from astropy import units as u
from crispy_forms.bootstrap import Accordion, AccordionGroup, TabHolder, Tab, Alert
from crispy_forms.layout import Div, HTML, Layout, ButtonHolder, Submit
from dateutil.parser import parse
from django import forms
from django.conf import settings
from django.core.cache import cache

from tom_common.exceptions import ImproperCredentialsException
from tom_observations.cadence import CadenceForm
from tom_observations.facility import BaseRoboticObservationFacility, BaseRoboticObservationForm, get_service_class
from tom_observations.observation_template import GenericTemplateForm
from tom_targets.models import Target
from tom_targets.base_models import REQUIRED_NON_SIDEREAL_FIELDS, REQUIRED_NON_SIDEREAL_FIELDS_PER_SCHEME

logger = logging.getLogger(__name__)


class OCSSettings():
    """ Class encapsulates the settings from django for this Facility, and some of the options for
        an OCS form implementation. The facility_name is used for retrieving the settings from the
        FACILITIES dictionary in settings.py.
    """
    default_settings = {
        'portal_url': '',
        'archive_url': '',
        'api_key': '',
        'max_instrument_configs': 5,
        'max_configurations': 5
    }
    default_instrument_config = {'No Instrument Found': {
        'type': 'NONE',
        'optical_elements': {'filters': [{
                'name': 'Unknown Filter',
                'code': 'unknown',
                'schedulable': True,
                'default': True}]},
        'configuration_types': {
            'None': {
                'name': 'No Configurations found',
                'code': 'NONE',
            }
        },
        'default_configuration_type': 'None',
    }}

    # These class variables describe default help text for a variety of OCS fields.
    # Override them as desired for a specific OCS implementation.
    ipp_value_help = """
            Value between 0.5 to 2.0.
            <a href="https://lco.global/documents/20/the_new_priority_factor.pdf" target="_blank">
                More information about Intra Proprosal Priority (IPP).
            </a>
    """

    observation_mode_help = """
        <a href="https://lco.global/documentation/special-scheduling-modes/" target="_blank">
            More information about Rapid Response mode.
        </a>
    """

    optimization_type_help = """
        Scheduling optimization emphasis: Time for ASAP, or Airmass for minimum airmass.
    """

    end_help = ""

    instrument_type_help = ""

    exposure_time_help = ""

    max_lunar_phase_help = """
        Value between 0 (new moon) and 1 (full moon).
    """

    static_cadencing_help = """
        <em>Static cadence parameters.</em> Leave blank if no cadencing is desired.
    """

    repeat_duration_help = """
        The requested duration for this configuration to be repeated within.
        Only applicable to <em>* Sequence</em> configuration types.
    """

    max_airmass_help = """
        Maximum acceptable airmass at which the observation can be scheduled.
        A plane-parallel atmosphere is assumed.
    """

    def __init__(self, facility_name):
        self.facility_name = facility_name

    def get_setting(self, key):
        return settings.FACILITIES.get(self.facility_name, self.default_settings).get(key, self.default_settings[key])

    def get_unconfigured_settings(self):
        """
        Check that the settings for this facility are present, and return list of any required settings that are blank.
        """
        return [key for key in self.default_settings.keys() if not self.get_setting(key)]

    def get_observing_states(self):
        return [
            'PENDING', 'COMPLETED', 'WINDOW_EXPIRED', 'CANCELED', 'FAILURE_LIMIT_REACHED', 'NOT_ATTEMPTED'
        ]

    def get_pending_observing_states(self):
        return ['PENDING']

    def get_successful_observing_states(self):
        return ['COMPLETED']

    def get_failed_observing_states(self):
        return ['WINDOW_EXPIRED', 'CANCELED', 'FAILURE_LIMIT_REACHED', 'NOT_ATTEMPTED']

    def get_terminal_observing_states(self):
        return self.get_successful_observing_states() + self.get_failed_observing_states()

    def get_fits_facility_header_keyword(self):
        """ Should return the fits header keyword that stores what facility the data was taken at
        """
        return 'ORIGIN'

    def get_fits_facility_header_value(self):
        """ Should return the expected value in the fits facility header for data from this facility
        """
        return 'OCS'

    def get_fits_header_dateobs_keyword(self):
        """ Should return the fits header keyword that stores the date the data was taken at
        """
        return 'DATE-OBS'

    def get_data_flux_constant(self):
        return (1e-15 * u.erg) / (u.cm ** 2 * u.second * u.angstrom)

    def get_data_wavelength_units(self):
        return u.angstrom

    def get_sites(self):
        """
        Return an iterable of dictionaries that contain the information
        necessary to be used in the planning (visibility) tool.
        Format:
        {
            'Site Name': {
                'sitecode': 'tst',
                'latitude': -31.272,
                'longitude': 149.07,
                'elevation': 1116
            },
        }
        """
        return {}

    def get_weather_urls(self):
        """ Return a dictionary containing urls to check the weather for each site in your sites dictionary
        Format:
        {
            'code': 'OCS',
            'sites': [
                {
                    'code': sitecode,
                    'weather_url': weather_url for site
                }
            ]
        }
        """
        return {
            'code': self.facility_name,
            'sites': []
        }


def make_request(*args, **kwargs):
    response = requests.request(*args, **kwargs)
    if 401 <= response.status_code <= 403:
        raise ImproperCredentialsException('OCS: ' + str(response.content))
    elif 400 == response.status_code:
        raise forms.ValidationError(f'OCS: {str(response.content)}')
    response.raise_for_status()
    return response


class OCSBaseForm(forms.Form):
    """ The OCSBaseForm assumes nothing of fields, and just adds helper methods for getting
        data from an OCS portal to other form subclasses.
    """
    def __init__(self, *args, **kwargs):
        if 'facility_settings' not in kwargs:
            kwargs['facility_settings'] = OCSSettings("OCS")
        self.facility_settings = kwargs.pop('facility_settings')
        super().__init__(*args, **kwargs)

    def target_group_choices(self, include_self=True):
        target_id = self.data.get('target_id')
        if not target_id:
            target_id = self.initial.get('target_id')
        try:
            target_name = Target.objects.get(pk=target_id).name
            group_targets = Target.objects.filter(targetlist__targets__pk=target_id).exclude(
                pk=target_id).order_by('name').distinct().values_list('pk', 'name')
            if include_self:
                return [(target_id, target_name)] + list(group_targets)
            else:
                return list(group_targets)
        except Target.DoesNotExist:
            return []

    def _get_instruments(self):
        cached_instruments = cache.get(f'{self.facility_settings.facility_name}_instruments')
        if not cached_instruments:
            logger.warning("Instruments not cached, getting them again!!!")
            try:
                response = make_request(
                    'GET',
                    urljoin(self.facility_settings.get_setting('portal_url'), '/api/instruments/'),
                    headers={'Authorization': 'Token {0}'.format(self.facility_settings.get_setting('api_key'))}
                )
                cached_instruments = {k: v for k, v in response.json().items()}
            except ImproperCredentialsException:
                cached_instruments = self.facility_settings.default_instrument_config
            cache.set(f'{self.facility_settings.facility_name}_instruments', cached_instruments, 3600)
        return cached_instruments

    def get_instruments(self):
        return self._get_instruments()

    def instrument_choices(self):
        return sorted([(k, v.get('name')) for k, v in self.get_instruments().items()], key=lambda inst: inst[1])

    def mode_choices(self, mode_type, use_code_only=False):
        return sorted(set([
            (f['code'], f['code'] if use_code_only else f['name']) for ins in self.get_instruments().values() for f in
            ins.get('modes', {}).get(mode_type, {}).get('modes', [])
        ]), key=lambda filter_tuple: filter_tuple[1])

    def filter_choices_for_group(self, oe_group, use_code_only=False):
        return sorted(set([
            (f['code'], f['code'] if use_code_only else f['name']) for ins in self.get_instruments().values() for f in
            ins['optical_elements'].get(oe_group, []) if f.get('schedulable')
        ]), key=lambda filter_tuple: filter_tuple[1])

    def instrument_to_default_configuration_type(self, instrument_type):
        return self.get_instruments().get(instrument_type, {}).get('default_configuration_type', '')

    def all_optical_element_choices(self, use_code_only=False):
        optical_elements = set()
        for ins in self.get_instruments().values():
            for oe_group in ins.get('optical_elements', {}).values():
                for element in oe_group:
                    if element.get('schedulable'):
                        optical_elements.add((element['code'], element['code'] if use_code_only else element['name']))
        return sorted(optical_elements, key=lambda x: x[1])

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

    def proposal_choices(self):
        cached_proposals = cache.get(f'{self.facility_settings.facility_name}_proposals')
        if not cached_proposals:
            try:
                response = make_request(
                    'GET',
                    urljoin(self.facility_settings.get_setting('portal_url'), '/api/profile/'),
                    headers={'Authorization': 'Token {0}'.format(self.facility_settings.get_setting('api_key'))}
                )
            except ImproperCredentialsException:
                return [(0, 'No proposals found')]
            cached_proposals = []
            for p in response.json()['proposals']:
                if p['current']:
                    cached_proposals.append((p['id'], '{} ({})'.format(p['title'], p['id'])))
            cache.set(f'{self.facility_settings.facility_name}_proposals', cached_proposals, 3600)
        return cached_proposals


class OCSTemplateBaseForm(GenericTemplateForm, OCSBaseForm):
    ipp_value = forms.FloatField()
    exposure_count = forms.IntegerField(min_value=1)
    exposure_time = forms.FloatField(min_value=0.1)
    max_airmass = forms.FloatField()

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['proposal'] = forms.ChoiceField(choices=self.proposal_choices())
        self.fields['filter'] = forms.ChoiceField(choices=self.all_optical_element_choices())
        self.fields['instrument_type'] = forms.ChoiceField(choices=self.instrument_choices())
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


class OCSAdvancedExpansionsLayout(Layout):
    def __init__(self, form_name, facility_settings, *args, **kwargs):
        self.facility_settings = facility_settings
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
                            HTML(f'''<br/><p>{self.facility_settings.static_cadencing_help}</p>'''),
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


class OCSConfigurationLayout(Layout):
    def __init__(self, form_name, facility_settings, instrument_config_layout_class, oe_groups, *args, **kwargs):
        self.form_name = form_name
        self.facility_settings = facility_settings
        self.instrument_config_layout_class = instrument_config_layout_class
        super().__init__(
            Div(
                HTML('''<br/><h2>Configurations:</h2>''')
            ),
            TabHolder(
                *self._get_config_tabs(oe_groups, facility_settings.get_setting('max_configurations'))
            )
        )

    def _get_config_tabs(self, oe_groups, num_tabs):
        tabs = []
        for i in range(num_tabs):
            tabs.append(
                Tab(f'{i+1}',
                    *self._get_config_layout(i + 1, oe_groups),
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
                *self.get_initial_accordion_items(instance),
                AccordionGroup('Instrument Configurations',
                               self.instrument_config_layout_class(self.form_name, self.facility_settings,
                                                                   instance, oe_groups),
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
                *self.get_final_accordion_items(instance)
            )
        )

    def get_initial_accordion_items(self, instance):
        """ Override in subclasses to add items to the begining of the accordion group
        """
        return ()

    def get_final_accordion_items(self, instance):
        """ Override in the subclasses to add items at the end of the accordion group
        """
        return ()

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


class OCSInstrumentConfigLayout(Layout):
    def __init__(self, form_name, facility_settings, config_instance, oe_groups, *args, **kwargs):
        self.form_name = form_name
        self.facility_settings = facility_settings
        super().__init__(
            TabHolder(
                *self._get_ic_tabs(config_instance, oe_groups, facility_settings.get_setting('max_instrument_configs'))
            )
        )

    def _get_ic_tabs(self, config_instance, oe_groups, num_tabs):
        tabs = []
        for i in range(num_tabs):
            tabs.append(
                Tab(f'{i+1}',
                    *self._get_ic_layout(config_instance, i + 1, oe_groups),
                    css_id=f'{self.form_name}_c_{config_instance}_ic_{i+1}'
                    ),
            )
        return tuple(tabs)

    def _get_oe_groups_layout(self, config_instance, instance, oe_groups):
        oe_groups_layout = []
        for oe_group1, oe_group2 in zip(*[iter(oe_groups)] * 2):
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

    def get_initial_ic_items(self, config_instance, instance):
        """ Override in subclasses to add items to the begining of the inst config
        """
        return ()

    def get_final_ic_items(self, config_instance, instance):
        """ Override in the subclasses to add items at the end of the inst config
        """
        return ()

    def _get_ic_layout(self, config_instance, instance, oe_groups):
        return (
            *self.get_initial_ic_items(config_instance, instance),
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
            *self._get_oe_groups_layout(config_instance, instance, oe_groups),
            *self.get_final_ic_items(config_instance, instance)
        )


class OCSBaseObservationForm(BaseRoboticObservationForm, OCSBaseForm):
    """
    The OCSBaseObservationForm provides the base set of utilities to construct an observation at an OCS facility.
    It must be subclassed to be used, as some methods are not implemented in this class.
    """
    name = forms.CharField()
    start = forms.CharField(widget=forms.TextInput(attrs={'type': 'date'}))
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
        self.fields['ipp_value'] = forms.FloatField(
            label='Intra Proposal Priority (IPP factor)',
            min_value=0.5,
            max_value=2,
            initial=1.05,
            help_text=self.facility_settings.ipp_value_help
        )
        self.fields['end'] = forms.CharField(widget=forms.TextInput(attrs={'type': 'date'}),
                                             help_text=self.facility_settings.end_help)
        self.fields['observation_mode'] = forms.ChoiceField(
            choices=(('NORMAL', 'Normal'), ('RAPID_RESPONSE', 'Rapid-Response'), ('TIME_CRITICAL', 'Time-Critical')),
            help_text=self.facility_settings.observation_mode_help
        )
        self.fields['optimization_type'] = forms.ChoiceField(
            choices=(('TIME', 'Time'), ('AIRMASS', 'Airmass')),
            required=False,
            help_text=self.facility_settings.optimization_type_help
        )
        # self.helper.layout = Layout(
        #     self.common_layout,
        #     self.layout(),
        #     self.button_layout()
        # )

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
            # Mapping from TOM field names to OCS API field names, for fields
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
                ocs_field = field_mapping.get(field, field)
                target_fields[ocs_field] = getattr(target, field)

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

    def _build_instrument_configs(self):
        return []

    def _build_configuration(self):
        configuration = {
            'type': self.instrument_to_default_configuration_type(self.cleaned_data['instrument_type']),
            'instrument_type': self.cleaned_data['instrument_type'],
            'target': self._build_target_fields(self.cleaned_data['target_id']),
            'instrument_configs': self._build_instrument_configs(),
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

        # use the OCS Observation Portal candence builder to build the candence
        response = make_request(
            'POST',
            urljoin(self.facility_settings.get_setting('portal_url'), '/api/requestgroups/cadence/'),
            json=payload,
            headers={'Authorization': 'Token {0}'.format(self.facility_settings.get_setting('api_key'))}
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


class OCSFullObservationForm(OCSBaseObservationForm):
    """
    The OCSFullObservationForm has all capabilities to construct an observation using the OCS Request language.
    While the forms that inherit from it provide a subset of instruments and filters, the
    OCSFullObservationForm presents the user with all of the instrument and filter options that the facility has to
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

    def __init__(self, *args, **kwargs):
        # Need to load the facility_settings here even though it gets loaded in super __init__
        # So that we can modify the initial data before hitting the base __init__
        self.facility_settings = kwargs.get('facility_settings', OCSSettings("OCS"))
        if 'initial' in kwargs:
            kwargs['initial'] = self.load_initial_from_template(kwargs['initial'])
        super().__init__(*args, **kwargs)
        for j in range(self.facility_settings.get_setting('max_configurations')):
            self.fields[f'c_{j+1}_instrument_type'] = forms.ChoiceField(
                choices=self.instrument_choices(), required=False,
                help_text=self.facility_settings.instrument_type_help,
                label='Instrument Type')
            self.fields[f'c_{j+1}_configuration_type'] = forms.ChoiceField(
                choices=self.configuration_type_choices(), required=False, label='Configuration Type')
            self.fields[f'c_{j+1}_repeat_duration'] = forms.FloatField(
                help_text=self.facility_settings.repeat_duration_help, required=False, label='Repeat Duration',
                widget=forms.TextInput(attrs={'placeholder': 'Seconds'}))
            self.fields[f'c_{j+1}_max_airmass'] = forms.FloatField(
                help_text=self.facility_settings.max_airmass_help, label='Max Airmass', min_value=0, initial=1.6,
                required=False)
            self.fields[f'c_{j+1}_min_lunar_distance'] = forms.IntegerField(
                min_value=0, label='Minimum Lunar Distance', required=False)
            self.fields[f'c_{j+1}_max_lunar_phase'] = forms.FloatField(
                help_text=self.facility_settings.max_lunar_phase_help, min_value=0, max_value=1.0,
                label='Maximum Lunar Phase', required=False)
            self.fields[f'c_{j+1}_target_override'] = forms.ChoiceField(
                choices=self.target_group_choices(),
                required=False,
                help_text='Set a different target for this configuration. Must be in the same target group.',
                label='Substitute Target for this Configuration'
            )
            for i in range(self.facility_settings.get_setting('max_instrument_configs')):
                self.fields[f'c_{j + 1}_ic_{i + 1}_readout_mode'] = forms.ChoiceField(
                    choices=self.mode_choices('readout'), required=False, label='Readout Mode')
                self.fields[f'c_{j+1}_ic_{i+1}_exposure_count'] = forms.IntegerField(
                    min_value=1, label='Exposure Count', initial=1, required=False)
                self.fields[f'c_{j+1}_ic_{i+1}_exposure_time'] = forms.FloatField(
                    min_value=0.1, label='Exposure Time',
                    widget=forms.TextInput(attrs={'placeholder': 'Seconds'}),
                    help_text=self.facility_settings.exposure_time_help, required=False)
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

    def button_layout(self):
        """
        Override Button layout from BaseObservationForm.
        Submit button will be disabled if there are any unconfigured settings found by get_unconfigured_settings().
        """
        target_id = self.initial.get('target_id')

        return ButtonHolder(
            Submit('submit', 'Submit', disabled=bool(self.facility_settings.get_unconfigured_settings())),
            Submit('validate', 'Validate'),
            HTML(f'''<a class="btn btn-outline-primary" href="{{% url 'tom_targets:detail' {target_id} %}}?tab=observe">
                        Back</a>''')
        )

    def form_name(self):
        return 'base'

    def instrument_config_layout_class(self):
        return OCSInstrumentConfigLayout

    def configuration_layout_class(self):
        return OCSConfigurationLayout

    def advanced_expansions_layout_class(self):
        return OCSAdvancedExpansionsLayout

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
                self.form_name(), self.facility_settings, self.instrument_config_layout_class(),
                self.get_optical_element_groups()
            ),
            self.advanced_expansions_layout_class()(self.form_name(), self.facility_settings)
        )

    def load_initial_from_template(self, initial):
        """ Template data contains single fields like 'exposure_time' so convert those into the per config/ic versions
        """
        if not initial:
            return initial
        if 'template_name' in initial:
            if 'exposure_time' in initial:
                initial['c_1_ic_1_exposure_time'] = initial['exposure_time']
            if 'exposure_count' in initial:
                initial['c_1_ic_1_exposure_count'] = initial['exposure_count']
            if 'max_airmass' in initial:
                initial['c_1_max_airmass'] = initial['max_airmass']
            if 'instrument_type' in initial:
                initial['c_1_instrument_type'] = initial['instrument_type']
            if 'filter' in initial:
                for oe_group in self.get_optical_element_groups():
                    oe_group_plural = oe_group + 's'
                    filter_choices = self.filter_choices_for_group(oe_group_plural)
                    if initial['filter'] in [f[0] for f in filter_choices]:
                        initial[f'c_1_ic_1_{oe_group}'] = initial['filter']
        return initial

    def _build_instrument_config(self, instrument_type, configuration_id, instrument_config_id):
        # If the instrument config did not have an exposure time set, leave it out by returning None
        if not self.cleaned_data.get(f'c_{configuration_id}_ic_{instrument_config_id}_exposure_time'):
            return None
        instrument_config = {
            'exposure_count': self.cleaned_data[f'c_{configuration_id}_ic_{instrument_config_id}_exposure_count'],
            'exposure_time': self.cleaned_data[f'c_{configuration_id}_ic_{instrument_config_id}_exposure_time'],
            'optical_elements': {},
            'mode': self.cleaned_data[f'c_{configuration_id}_ic_{instrument_config_id}_readout_mode']
        }
        for oe_group in self.get_optical_element_groups():
            instrument_config['optical_elements'][oe_group] = self.cleaned_data.get(
                f'c_{configuration_id}_ic_{instrument_config_id}_{oe_group}')

        return instrument_config

    def _build_instrument_configs(self, instrument_type, configuration_id):
        ics = []
        for i in range(self.facility_settings.get_setting('max_instrument_configs')):
            ic = self._build_instrument_config(instrument_type, configuration_id, i + 1)
            # This will only include instrument configs with an exposure time set
            if ic:
                ics.append(ic)

        return ics

    def _build_configuration(self, build_id):
        instrument_configs = self._build_instrument_configs(
            self.cleaned_data[f'c_{build_id}_instrument_type'], build_id
            )
        # Check if the instrument configs are empty, and if so, leave this configuration out by returning None
        if not instrument_configs:
            return None
        configuration = {
            'type': self.cleaned_data[f'c_{build_id}_configuration_type'],
            'instrument_type': self.cleaned_data[f'c_{build_id}_instrument_type'],
            'instrument_configs': instrument_configs,
            'acquisition_config': self._build_acquisition_config(build_id),
            'guiding_config': self._build_guiding_config(build_id),
            'constraints': {
                'max_airmass': self.cleaned_data[f'c_{build_id}_max_airmass'],
            }
        }
        if self.cleaned_data.get(f'c_{build_id}_target_override'):
            configuration['target'] = self._build_target_fields(self.cleaned_data[f'c_{build_id}_target_override'])
        else:
            configuration['target'] = self._build_target_fields(self.cleaned_data['target_id'])
        if self.cleaned_data.get(f'c_{build_id}_repeat_duration'):
            configuration['repeat_duration'] = self.cleaned_data[f'c_{build_id}_repeat_duration']
        if self.cleaned_data.get(f'c_{build_id}_min_lunar_distance'):
            configuration['constraints']['min_lunar_distance'] = self.cleaned_data[f'c_{build_id}_min_lunar_distance']
        if self.cleaned_data.get(f'c_{build_id}_max_lunar_phase'):
            configuration['constraints']['max_lunar_phase'] = self.cleaned_data[f'c_{build_id}_max_lunar_phase']

        return configuration

    def _build_configurations(self):
        configurations = []
        for j in range(self.facility_settings.get_setting('max_configurations')):
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
        # Use the OCS Observation Portal dither pattern expansion to expand the configuration
        response_json = {}
        try:
            response = make_request(
                'POST',
                urljoin(self.facility_settings.get_setting('portal_url'), '/api/configurations/dither/'),
                json=payload,
                headers={'Authorization': 'Token {0}'.format(self.facility_settings.get_setting('api_key'))}
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

        # Use the OCS Observation Portal dither pattern expansion to expand the configuration
        response_json = {}
        try:
            response = make_request(
                'POST',
                urljoin(self.facility_settings.get_setting('portal_url'), '/api/requests/mosaic/'),
                json=payload,
                headers={'Authorization': 'Token {0}'.format(self.facility_settings.get_setting('api_key'))}
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


class OCSFacility(BaseRoboticObservationFacility):
    """
    The ``OCSFacility`` is the interface to an OCS Observation Portal. For information regarding
    OCS observing and the available parameters, please see https://observatorycontrolsystem.github.io/.
    """
    name = 'OCS'
    observation_forms = {
        'ALL': OCSFullObservationForm,
    }

    def __init__(self, facility_settings=OCSSettings('OCS')):
        self.facility_settings = facility_settings
        super().__init__()

    # TODO: this should be called get_form_class
    def get_form(self, observation_type):
        return self.observation_forms.get(observation_type, OCSFullObservationForm)

    # TODO: this should be called get_template_form_class
    def get_template_form(self, observation_type):
        return OCSTemplateBaseForm

    def submit_observation(self, observation_payload):
        response = make_request(
            'POST',
            urljoin(self.facility_settings.get_setting('portal_url'), '/api/requestgroups/'),
            json=observation_payload,
            headers=self._portal_headers()
        )
        return [r['id'] for r in response.json()['requests']]

    def validate_observation(self, observation_payload):
        response = make_request(
            'POST',
            urljoin(self.facility_settings.get_setting('portal_url'), '/api/requestgroups/validate/'),
            json=observation_payload,
            headers=self._portal_headers()
        )
        return response.json()

    def cancel_observation(self, observation_id):
        requestgroup_id = self._get_requestgroup_id(observation_id)

        response = make_request(
            'POST',
            urljoin(self.facility_settings.get_setting('portal_url'), f'/api/requestgroups/{requestgroup_id}/cancel/'),
            headers=self._portal_headers()
        )

        return response.json()['state'] == 'CANCELED'

    def get_observation_url(self, observation_id):
        return urljoin(self.facility_settings.get_setting('portal_url'), f'/requests/{observation_id}')

    def get_flux_constant(self):
        return self.facility_settings.get_data_flux_constant()

    def get_wavelength_units(self):
        return self.facility_settings.get_data_wavelength_units()

    def get_date_obs_from_fits_header(self, header):
        return header.get(self.facility_settings.get_fits_header_dateobs_keyword(), None)

    def is_fits_facility(self, header):
        """
        Returns True if the keyword is in the given FITS header and contains the value specified, False
        otherwise.

        :param header: FITS header object
        :type header: dictionary-like

        :returns: True if header matches your OCS facility, False otherwise
        :rtype: boolean
        """
        return (self.facility_settings.get_fits_facility_header_value() == header.get(
                self.facility_settings.get_fits_facility_header_keyword(), None))

    def get_start_end_keywords(self):
        return ('start', 'end')

    def get_terminal_observing_states(self):
        return self.facility_settings.get_terminal_observing_states()

    def get_failed_observing_states(self):
        return self.facility_settings.get_failed_observing_states()

    def get_observing_sites(self):
        return self.facility_settings.get_sites()

    def get_facility_weather_urls(self):
        """
        `facility_weather_urls = {'code': 'XYZ', 'sites': [ site_dict, ... ]}`
        where
        `site_dict = {'code': 'XYZ', 'weather_url': 'http://path/to/weather'}`
        """
        return self.facility_settings.get_weather_urls()

    def get_facility_status(self):
        """
        Get the telescope_states from the OCS API endpoint and simply
        transform the returned JSON into the following dictionary hierarchy
        for use by the facility_status.html template partial.

        facility_dict = {'code': 'OCS', 'sites': [ site_dict, ... ]}
        site_dict = {'code': 'XYZ', 'telescopes': [ telescope_dict, ... ]}
        telescope_dict = {'code': 'XYZ', 'status': 'AVAILABILITY'}

        Here's an example of the returned dictionary:

        literal_facility_status_example = {
            'code': 'OCS',
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
        # make the request to the OCS API for the telescope_states
        now = datetime.now()
        telescope_states = {}
        try:
            response = make_request(
                'GET',
                urljoin(self.facility_settings.get_setting('portal_url'), '/api/telescope_states/'),
                headers=self._portal_headers()
            )
            response.raise_for_status()
            telescope_states = response.json()
            logger.info(f"Telescope states took {(datetime.now() - now).total_seconds()}")
        except (requests.exceptions.HTTPError, requests.exceptions.ConnectionError) as e:
            logger.warning(f"Error retrieving telescope_states from OCS for facility status: {repr(e)}")
        # Now, transform the telescopes_state dictionary in a dictionary suitable
        # for the facility_status.html template partial.

        # set up the return value to be populated by the for loop below
        facility_status = {
            'code': self.name,
            'sites': []
        }
        site_list = [site["sitecode"] for site in self.get_observing_sites().values()]

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
            urljoin(self.facility_settings.get_setting('portal_url'), f'/api/requests/{observation_id}'),
            headers=self._portal_headers()
        )
        state = response.json()['state']

        response = make_request(
            'GET',
            urljoin(self.facility_settings.get_setting('portal_url'), f'/api/requests/{observation_id}/observations/'),
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
        if self.facility_settings.get_setting('api_key'):
            return {'Authorization': f'Token {self.facility_settings.get_setting("api_key")}'}
        else:
            return {}

    def _get_requestgroup_id(self, observation_id):
        query_params = urlencode({'request_id': observation_id})

        response = make_request(
            'GET',
            urljoin(self.facility_settings.get_setting('portal_url'), f'/api/requestgroups?{query_params}'),
            headers=self._portal_headers()
        )
        requestgroups = response.json()

        if requestgroups['count'] == 1:
            return requestgroups['results'][0]['id']

    def _archive_frames(self, observation_id, product_id=None):
        frames = []
        if product_id:
            response = make_request(
                'GET',
                urljoin(self.facility_settings.get_setting('archive_url'), f'/frames/{product_id}/'),
                headers=self._portal_headers()
            )
            frames = [response.json()]
        else:
            url = urljoin(self.facility_settings.get_setting('archive_url'),
                          f'/frames/?REQNUM={observation_id}&limit=1000')
            while url:
                response = make_request(
                    'GET',
                    url,
                    headers=self._portal_headers()
                )
                frames.extend(response.json()['results'])
                url = response.json()['next']
        return frames
