from datetime import datetime, timedelta
import requests

from astropy import units as u
from crispy_forms.bootstrap import PrependedText
from crispy_forms.layout import Column, Div, HTML, Layout, Row
from dateutil.parser import parse
from django import forms
from django.conf import settings
from django.core.cache import cache

from tom_common.exceptions import ImproperCredentialsException
from tom_observations.cadence import CadenceForm
from tom_observations.facility import BaseRoboticObservationFacility, BaseRoboticObservationForm, get_service_class
from tom_observations.observing_strategy import GenericStrategyForm
from tom_observations.widgets import FilterField
from tom_targets.models import Target, REQUIRED_NON_SIDEREAL_FIELDS, REQUIRED_NON_SIDEREAL_FIELDS_PER_SCHEME

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
SUCCESSFUL_OBSERVING_STATES = ['COMPLETED']
FAILED_OBSERVING_STATES = ['WINDOW_EXPIRED', 'CANCELED']
TERMINAL_OBSERVING_STATES = SUCCESSFUL_OBSERVING_STATES + FAILED_OBSERVING_STATES

# Units of flux and wavelength for converting to Specutils Spectrum1D objects
FLUX_CONSTANT = (1e-15 * u.erg) / (u.cm ** 2 * u.second * u.angstrom)
WAVELENGTH_UNITS = u.angstrom

# FITS header keywords used for data processing
FITS_FACILITY_KEYWORD = 'ORIGIN'
FITS_FACILITY_KEYWORD_VALUE = 'LCOGT'
FITS_FACILITY_DATE_OBS_KEYWORD = 'DATE-OBS'

# Functions needed specifically for LCO
# Helpers for LCO fields
ipp_value_help = """
        Value between 0.5 to 2.0.
        <a href="https://lco.global/documents/20/the_new_priority_factor.pdf">
            More information about Intra Proprosal Priority (IPP).
        </a>.
"""

observation_mode_help = """
    <a href="https://lco.global/documentation/special-scheduling-modes/">
        More information about Rapid Response mode.
    </a>
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


def make_request(*args, **kwargs):
    response = requests.request(*args, **kwargs)
    if 400 <= response.status_code < 500:
        raise ImproperCredentialsException('LCO: ' + str(response.content))
    response.raise_for_status()
    return response


class LCOBaseForm(forms.Form):
    ipp_value = forms.FloatField()
    exposure_count = forms.IntegerField(min_value=1)
    exposure_time = forms.FloatField(min_value=0.1)
    max_airmass = forms.FloatField()

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['proposal'] = forms.ChoiceField(choices=self.proposal_choices())
        self.fields['filter'] = forms.ChoiceField(choices=self.filter_choices())
        self.fields['instrument_type'] = forms.ChoiceField(choices=self.instrument_choices())

    def _get_instruments(self):
        cached_instruments = cache.get('lco_instruments')

        if not cached_instruments:
            response = make_request(
                'GET',
                PORTAL_URL + '/api/instruments/',
                headers={'Authorization': 'Token {0}'.format(LCO_SETTINGS['api_key'])}
            )
            cached_instruments = {k: v for k, v in response.json().items() if 'SOAR' not in k}
            cache.set('lco_instruments', cached_instruments)

        return cached_instruments

    def instrument_choices(self):
        return [(k, v['name']) for k, v in self._get_instruments().items()]

    def filter_choices(self):
        return set([
            (f['code'], f['name']) for ins in self._get_instruments().values() for f in
            ins['optical_elements'].get('filters', []) + ins['optical_elements'].get('slits', [])
            ])

    def proposal_choices(self):
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


class LCOBaseObservationForm(BaseRoboticObservationForm, LCOBaseForm, CadenceForm):
    """
    The LCOBaseObservationForm provides the base set of utilities to construct an observation at Las Cumbres
    Observatory. While the forms that inherit from it provide a subset of instruments and filters, the
    LCOBaseObservationForm presents the user with all of the instrument and filter options that the facility has to
    offer.
    """
    name = forms.CharField()
    ipp_value = forms.FloatField(label='Intra Proposal Priority (IPP factor)',
                                 min_value=0.5,
                                 max_value=2,
                                 help_text=ipp_value_help)
    start = forms.CharField(widget=forms.TextInput(attrs={'type': 'date'}))
    end = forms.CharField(widget=forms.TextInput(attrs={'type': 'date'}),
                          help_text=end_help)
    exposure_count = forms.IntegerField(min_value=1)
    exposure_time = forms.FloatField(min_value=0.1,
                                     widget=forms.TextInput(attrs={'placeholder': 'Seconds'}),
                                     help_text=exposure_time_help)
    max_airmass = forms.FloatField(help_text=max_airmass_help)
    min_lunar_distance = forms.IntegerField(min_value=0, label='Minimum Lunar Distance', required=False)
    period = forms.FloatField(required=False)
    jitter = forms.FloatField(required=False)
    observation_mode = forms.ChoiceField(
        choices=(('NORMAL', 'Normal'), ('TARGET_OF_OPPORTUNITY', 'Rapid Response')),
        help_text=observation_mode_help
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.helper.layout = Layout(
            self.common_layout,
            self.layout(),
            self.cadence_layout,
            self.button_layout()
        )

    def layout(self):
        return Div(
            Div(
                Div(
                    'name', 'proposal', 'ipp_value', 'observation_mode', 'start', 'end',
                    css_class='col'
                ),
                Div(
                    'filter', 'instrument_type', 'exposure_count', 'exposure_time', 'max_airmass', 'min_lunar_distance',
                    css_class='col'
                ),
                css_class='form-row',
            ),
            Div(
                HTML('<p>Cadence parameters. Leave blank if no cadencing is desired.</p>'),
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
        )

    def clean_start(self):
        start = self.cleaned_data['start']
        return parse(start).isoformat()

    def clean_end(self):
        end = self.cleaned_data['end']
        return parse(end).isoformat()

    def is_valid(self):
        super().is_valid()
        obs_module = get_service_class(self.cleaned_data['facility'])
        errors = obs_module().validate_observation(self.observation_payload())
        if errors:
            self.add_error(None, self._flatten_error_dict(errors))
        return not errors

    def _flatten_error_dict(self, error_dict):
        non_field_errors = []
        for k, v in error_dict.items():
            if type(v) == list:
                for i in v:
                    if type(i) == str:
                        if k in self.fields:
                            self.add_error(k, i)
                        else:
                            non_field_errors.append('{}: {}'.format(k, i))
                    if type(i) == dict:
                        non_field_errors.append(self._flatten_error_dict(i))
            elif type(v) == str:
                if k in self.fields:
                    self.add_error(k, v)
                else:
                    non_field_errors.append('{}: {}'.format(k, v))
            elif type(v) == dict:
                non_field_errors.append(self._flatten_error_dict(v))

        return non_field_errors

    def instrument_to_type(self, instrument_type):
        if 'FLOYDS' in instrument_type:
            return 'SPECTRUM'
        elif 'NRES' in instrument_type:
            return 'NRES_SPECTRUM'
        else:
            return 'EXPOSE'

    def _build_target_fields(self):
        target = Target.objects.get(pk=self.cleaned_data['target_id'])
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

        return target_fields

    def _build_instrument_config(self):
        instrument_config = {
            'exposure_count': self.cleaned_data['exposure_count'],
            'exposure_time': self.cleaned_data['exposure_time'],
            'optical_elements': {
                'filter': self.cleaned_data['filter']
            }
        }

        return [instrument_config]

    def _build_configuration(self):
        return {
            'type': self.instrument_to_type(self.cleaned_data['instrument_type']),
            'instrument_type': self.cleaned_data['instrument_type'],
            'target': self._build_target_fields(),
            'instrument_configs': self._build_instrument_config(),
            'acquisition_config': {

            },
            'guiding_config': {

            },
            'constraints': {
                'max_airmass': self.cleaned_data['max_airmass']
            }
        }

    def _expand_cadence_request(self, payload):
        payload['requests'][0]['cadence'] = {
            'start': self.cleaned_data['start'],
            'end': self.cleaned_data['end'],
            'period': self.cleaned_data['period'],
            'jitter': self.cleaned_data['jitter']
        }
        payload['requests'][0]['windows'] = []
        response = make_request(
            'POST',
            PORTAL_URL + '/api/requestgroups/cadence/',
            json=payload,
            headers={'Authorization': 'Token {0}'.format(LCO_SETTINGS['api_key'])}
        )
        return response.json()

    def observation_payload(self):
        payload = {
            "name": self.cleaned_data['name'],
            "proposal": self.cleaned_data['proposal'],
            "ipp_value": self.cleaned_data['ipp_value'],
            "operator": "SINGLE",
            "observation_type": self.cleaned_data['observation_mode'],
            "requests": [
                {
                    "configurations": [self._build_configuration()],
                    "windows": [
                        {
                            "start": self.cleaned_data['start'],
                            "end": self.cleaned_data['end']
                        }
                    ],
                    "location": {
                        "telescope_class": self._get_instruments()[self.cleaned_data['instrument_type']]['class']
                    }
                }
            ]
        }
        if self.cleaned_data.get('period') and self.cleaned_data.get('jitter'):
            payload = self._expand_cadence_request(payload)

        return payload


class LCOImagingObservationForm(LCOBaseObservationForm):
    """
    The LCOImagingObservationForm allows the selection of parameters for observing using LCO's Imagers. The list of
    Imagers and their details can be found here: https://lco.global/observatory/instruments/
    """
    def instrument_choices(self):
        return [(k, v['name']) for k, v in self._get_instruments().items() if 'IMAGE' in v['type']]

    def filter_choices(self):
        return set([
            (f['code'], f['name']) for ins in self._get_instruments().values() for f in
            ins['optical_elements'].get('filters', [])
            ])


class LCOSpectroscopyObservationForm(LCOBaseObservationForm):
    """
    The LCOSpectroscopyObservationForm allows the selection of parameters for observing using LCO's Spectrographs. The
    list of spectrographs and their details can be found here: https://lco.global/observatory/instruments/
    """
    rotator_angle = forms.FloatField(min_value=0.0, initial=0.0)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['filter'].label = 'Slit'

    def layout(self):
        return Div(
            Div(
                Div(
                    'name', 'proposal', 'ipp_value', 'observation_mode', 'start', 'end',
                    css_class='col'
                ),
                Div(
                    'filter', 'instrument_type', 'exposure_count', 'exposure_time', 'max_airmass', 'rotator_angle',
                    css_class='col'
                ),
                css_class='form-row',
            ),
            Div(
                Div(
                    HTML('<p>Cadence parameters. Leave blank if no cadencing is desired.</p>'),
                    css_class='row'
                ),
                Div(
                    Div(
                        'period', 'jitter',
                        css_class='col'
                    ),
                    css_class='form-row'
                )
            )
        )

    def instrument_choices(self):
        return [(k, v['name']) for k, v in self._get_instruments().items() if 'SPECTRA' in v['type']]

    # NRES does not take a slit, and therefore needs an option of None
    def filter_choices(self):
        return set([
            (f['code'], f['name']) for ins in self._get_instruments().values() for f in
            ins['optical_elements'].get('slits', [])
            ] + [('None', 'None')])

    def _build_instrument_config(self):
        instrument_configs = super()._build_instrument_config()
        if self.cleaned_data['filter'] != 'None':
            instrument_configs[0]['optical_elements'] = {
                'slit': self.cleaned_data['filter']
            }
        else:
            instrument_configs[0].pop('optical_elements')
        instrument_configs[0]['rotator_mode'] = 'VFLOAT'  # TODO: Should be distinct field, SKY & VFLOAT are both valid
        instrument_configs[0]['extra_params'] = {
            'rotator_angle': self.cleaned_data['rotator_angle']
        }

        return instrument_configs


class LCOPhotometricSequenceForm(LCOBaseObservationForm):
    """
    The LCOPhotometricSequenceForm provides a form offering a subset of the parameters in the LCOImagingObservationForm.
    The form is modeled after the Supernova Exchange application's Photometric Sequence Request Form, and allows the
    configuration of multiple filters, as well as a more intuitive proactive cadence form.
    """
    filters = ['U', 'B', 'V', 'R', 'I', 'u', 'g', 'r', 'i', 'z', 'w']
    cadence_type = forms.ChoiceField(
        choices=[('once', 'Once in the next'), ('repeat', 'Repeating every')],
        required=True
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        # Add fields for each available filter as specified in the filters property
        for filter_name in self.filters:
            self.fields[filter_name] = FilterField(label=filter_name, required=False)

        # Massage cadence form to be SNEx-styled
        self.fields['cadence_strategy'].widget = forms.HiddenInput()
        self.fields['cadence_strategy'].required = False
        self.fields['cadence_frequency'].required = True
        self.fields['cadence_frequency'].widget.attrs['readonly'] = False
        self.fields['cadence_frequency'].widget.attrs['help_text'] = 'in hours'

        for field_name in ['exposure_time', 'exposure_count', 'start', 'end', 'filter']:
            self.fields.pop(field_name)
        if self.fields.get('groups'):
            self.fields['groups'].label = 'Data granted to'

        self.helper.layout = Layout(
            Div(
                Column('name'),
                Column('cadence_type'),
                Column('cadence_frequency'),
                css_class='form-row'
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
        for filter_name in self.filters:
            if len(self.cleaned_data[filter_name]) > 0:
                instrument_config.append({
                    'exposure_count': self.cleaned_data[filter_name][1],
                    'exposure_time': self.cleaned_data[filter_name][0],
                    'optical_elements': {
                        'filter': filter_name
                    }
                })

        return instrument_config

    def clean(self):
        """
        This clean method does the following:
            - Adds a start time of "right now", as the photometric sequence form does not allow for specification
              of a start time.
            - Adds an end time that corresponds with the cadence frequency
            - Adds the cadence strategy to the form if "repeat" was the selected "cadence_type". If "once" was
              selected, the observation is submitted as a single observation.
        """
        cleaned_data = super().clean()
        now = datetime.now()
        cleaned_data['start'] = datetime.strftime(datetime.now(), '%Y-%m-%dT%H:%M:%S')
        cleaned_data['end'] = datetime.strftime(now + timedelta(hours=cleaned_data['cadence_frequency']),
                                                '%Y-%m-%dT%H:%M:%S')
        if cleaned_data['cadence_type'] == 'repeat':
            cleaned_data['cadence_strategy'] = 'Resume Cadence After Failure'

        return cleaned_data

    def instrument_choices(self):
        """
        This method returns only the instrument choices available in the current SNEx photometric sequence form.
        """
        return [i for i in super().instrument_choices()
                if i[0] in ['1M0-SCICAM-SINISTRO', '0M4-SCICAM-SBIG', '2M0-SPECTRAL-AG']]

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
        for filter_name in self.filters:
            filter_layout.append(Row(filter_name))

        return Div(
            Div(
                filter_layout,
                css_class='col-md-6'
            ),
            Div(
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
            css_class='form-row'
        )


class LCOObservingStrategyForm(GenericStrategyForm, LCOBaseForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field_name in ['groups', 'target_id']:
            self.fields.pop(field_name, None)
        for field in self.fields:
            if field != 'strategy_name':
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
    observation_forms = {
        'IMAGING': LCOImagingObservationForm,
        'SPECTRA': LCOSpectroscopyObservationForm,
        'PHOTOMETRIC_SEQUENCE': LCOPhotometricSequenceForm
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

    def get_form(self, observation_type):
        try:
            return self.observation_forms[observation_type]
        except KeyError:
            return LCOBaseObservationForm

    def get_strategy_form(self, observation_type):
        return LCOObservingStrategyForm

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
        return response.json()['errors']

    def cancel_observation(self, observation_id):
        response = make_request(
            'POST',
            f'{PORTAL_URL}/api/requestgroups/{observation_id}/cancel/',
            headers=self._portal_headers()
        )
        return response.json()['errors']

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
            'code': 'LCO',
            'sites': []
        }

        for telescope_key, telescope_value in telescope_states.items():
            [site_code, _, _] = telescope_key.split('.')

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
