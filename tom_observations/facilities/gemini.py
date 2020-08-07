import requests
from django.conf import settings
from django import forms
from dateutil.parser import parse
from crispy_forms.layout import Div, HTML
from astropy import units as u

from tom_observations.facility import BaseRoboticObservationFacility, BaseRoboticObservationForm
from tom_common.exceptions import ImproperCredentialsException
from tom_targets.models import Target

try:
    GEM_SETTINGS = settings.FACILITIES['GEM']
except KeyError:
    GEM_SETTINGS = {
        'portal_url': {
            'GS': 'https://gsodb.gemini.edu:8443',
            'GN': 'https://gnodb.gemini.edu:8443',
        },
        'api_key': {
            'GS': '',
            'GN': '',
        },
        'user_email': '',
        'programs': {
            'GS-YYYYS-T-NNN': {
                'MM': 'Std: Some descriptive text',
                'NN': 'Rap: Some descriptive text'
            },
            'GN-YYYYS-T-NNN': {
                'QQ': 'Std: Some descriptive text',
                'PP': 'Rap: Some descriptive text',
            },
        },
    }

PORTAL_URL = GEM_SETTINGS['portal_url']
TERMINAL_OBSERVING_STATES = ['TRIGGERED', 'ON_HOLD']

# Units of flux and wavelength for converting to Specutils Spectrum1D objects
FLUX_CONSTANT = (1 * u.erg) / (u.cm ** 2 * u.second * u.angstrom)
WAVELENGTH_UNITS = u.angstrom

SITES = {
    'Cerro Pachon': {
        'sitecode': 'cpo',
        'latitude': -30.24075,
        'longitude': -70.736694,
        'elevation': 2722.
    },
    'Maunakea': {
        'sitecode': 'mko',
        'latitude': 19.8238,
        'longitude': -155.46905,
        'elevation': 4213.
    }
}


def make_request(*args, **kwargs):
    response = requests.request(*args, **kwargs)
    if 400 <= response.status_code < 500:
        print('Request failed: {}'.format(response.content))
        raise ImproperCredentialsException('GEM')
    response.raise_for_status()
    return response


def flatten_error_dict(form, error_dict):
    non_field_errors = []
    for k, v in error_dict.items():
        if type(v) == list:
            for i in v:
                if type(i) == str:
                    if k in form.fields:
                        form.add_error(k, i)
                    else:
                        non_field_errors.append('{}: {}'.format(k, i))
                if type(i) == dict:
                    non_field_errors.append(flatten_error_dict(form, i))
        elif type(v) == str:
            if k in form.fields:
                form.add_error(k, v)
            else:
                non_field_errors.append('{}: {}'.format(k, v))
        elif type(v) == dict:
            non_field_errors.append(flatten_error_dict(form, v))

    return non_field_errors


def proposal_choices():
    choices = []
    for p in GEM_SETTINGS['programs']:
        choices.append((p, p))
    return choices


def obs_choices():
    choices = []
    for p in GEM_SETTINGS['programs']:
        for obs in GEM_SETTINGS['programs'][p]:
            obsid = p + '-' + obs
            val = p.split('-')
            showtext = val[0][1] + val[1][2:] + val[2] + val[3] + '[' + obs + '] ' + GEM_SETTINGS['programs'][p][obs]
            choices.append((obsid, showtext))
    return choices


def get_site(progid, location=False):
    values = progid.split('-')
    gemloc = {'GS': 'Gemini South', 'GN': 'Gemini North'}
    site = values[0].upper()
    if location:
        site = gemloc[site]
    return site


class GEMObservationForm(BaseRoboticObservationForm):
    """
    The GEMObservationForm defines and collects the parameters for the Gemini
    Target of Opportunity (ToO) observation request API. The Gemini ToO process is described at

    https://www.gemini.edu/node/11005

    The team must have have an approved ToO program on Gemini and define ToO template observations,
    complete observations without defined targets, during the Phase 2 process. Authentication
    is done via a "User key" tied to an email address. See the following page for help on getting
    a user key and the password needed for the trigger request.

    https://www.gemini.edu/node/12109

    The following parameters are available.

    prog           - program id
    email          - email address for user key
    password       - password for user key associated with email, site specific, emailed by the ODB
    obsnum         - id of the template observation to clone and update, must be 'On Hold'
    target         - name of the target
    ra             - target RA [J2000], format 'HH:MM:SS.SS'
    dec            - target Dec[J2000], format 'DD:MM:SS.SSS'
    mags           - target magnitude information (optional)
    noteTitle      - title for the note, "Finding Chart" if not provided (optional)
    note           - text to include in a "Finding Chart" note (optional)
    posangle       - position angle [degrees E of N], defaults to 0 (optional)
    exptime        - exposure time [seconds], if not given then value in template used (optional)
    group          - name of the group for the new observation (optional)
    gstarget       - name of guide star (optional, but must be set if any gs* parameter given)
    gsra           - guide star RA [J2000] (optional, but must be set if any gs* parameter given)
    gsdec          - guide star Dec[J2000] (optional, but must be set if any gs* parameter given)
    gsmags         - guide star magnitude (optional)
    gsprobe        - PWFS1, PWFS2, OIWFS, or AOWFS (optional, but must be set if any gs* parameter given)
    ready          - if "true" set the status to "Prepared/Ready", otherwise remains at "On Hold" (default "true")
    windowDate     - interpreted in UTC in the format 'YYYY-MM-DD'
    windowTime     - interpreted in UTC in the format 'HH:MM'
    windowDuration - integer hours
    elevationType  - "none", "hourAngle", or "airmass"
    elevationMin   - minimum value for hourAngle/airmass
    elevationMax   - maximum value for hourAngle/airmass

    The server authenticates the request, finds the matching template
    observation, clones it, and then updates it with the remainder of the
    information.  That way the template observation can be reused in the
    future.  The target name, ra, and dec are straightforward.  The note
    text is added to a new note, the identified purpose of which is to
    contain a link to a finding chart.  The "ready" parameter is used to
    determine whether to mark the observation as "Prepared" (and thereby generate
    the TOO trigger) or keep it "On Hold".

    The exposure time parameter, if given, only sets the exposure time in the
    instrument "static component", which is tied to the first sequence step.
    Any exposure times defined in additional instrument iterators in the
    template observation sequence will not be changed. If the exposure time is not
    given then the value defined in the template observation is used. The
    exposure time must be an integer between 1 and 1200 seconds.

    If the group is specified and it does not exist (using a
    case-sensitive match) then a new group is created.

    The guide star ra, dec, and probe are optional but recommended since
    there is no guarantee, especially for GMOS, that a guide star will
    be available at the requested position angle. If no guide star is given
    then the OT will attempt to find a guide star. If any gs* parameter
    is specified, then gsra, gsdec, and gsprobe must all be specified.
    Otherwise an HTTP 400 (Bad Request) is returned with the message
    "guide star not completely specified".  If gstarget is missing or ""
    but other gs* parameters are present, then it defaults to "GS".

    If "target", "ra", or "dec" are missing, then an HTTP 400 (Bad
    Request) is returned with the name of the missing parameter.

    If any ra, dec, or guide probe parameter cannot be parsed, it also
    generates a bad request response.

    Magnitudes are optional, but when supplied must contain all three elements
    (value, band, system). Multiple magnitudes can be supplied; use a comma to
    delimit them (for example "24.2/U/Vega,23.4/r/AB"). Magnitudes can be specified
    in Vega, AB or Jy systems in the following bands: u, U, B, g, V, UC, r, R, i,
    I, z, Y, J, H, K, L, M, N, Q, AP.
    """

    # Form fields
    obsid = forms.MultipleChoiceField(choices=obs_choices())
    ready = forms.ChoiceField(initial='true', choices=(('true', 'Yes'), ('false', 'No')))
    brightness = forms.FloatField(required=False, label='Target Brightness')
    brightness_system = forms.ChoiceField(required=False,
                                          initial='AB',
                                          label='Brightness System',
                                          choices=(('Vega', 'Vega'), ('AB', 'AB'), ('Jy', 'Jy')))
    brightness_band = forms.ChoiceField(required=False,
                                        initial='r',
                                        label='Brightness Band',
                                        choices=(('u', 'u'), ('U', 'U'), ('B', 'B'), ('g', 'g'), ('V', 'V'),
                                                 ('UC', 'UC'), ('r', 'r'), ('R', 'R'), ('i', 'i'), ('I', 'I'),
                                                 ('z', 'z'), ('Y', 'Y'), ('J', 'J'), ('H', 'H'), ('K', 'K'),
                                                 ('L', 'L'), ('M', 'M'), ('N', 'N'), ('Q', 'Q'), ('AP', 'AP')))
    posangle = forms.FloatField(min_value=0.,
                                max_value=360.,
                                required=False,
                                initial=0.0,
                                label='Position Angle [0-360]')

    exptimes = forms.CharField(required=False, label='Exptime [s], comma separate')

    group = forms.CharField(required=False, label='Group Name')
    notetitle = forms.CharField(required=False, initial='Finding Chart', label='Note Title')
    note = forms.CharField(required=False, label='Note Text')

    eltype = forms.ChoiceField(required=False, label='Airmass/Hour Angle Constraint',
                               choices=(('none', 'None'), ('airmass', 'Airmass'), ('hourAngle', 'Hour Angle')))
    elmin = forms.FloatField(required=False, min_value=-5.0, max_value=5.0, label='Min Airmass/HA', initial=1.0)
    elmax = forms.FloatField(required=False, min_value=-5.0, max_value=5.0, label='Max Airmass/HA', initial=2.0)

    gstarg = forms.CharField(required=False, label='Guide Star Name')
    gsra = forms.CharField(required=False, label='Guide Star RA')
    gsdec = forms.CharField(required=False, label='Guide Star Dec')
    gsbrightness = forms.FloatField(required=False, label='Guide Star Brightness')
    gsbrightness_system = forms.ChoiceField(required=False,
                                            initial='Vega',
                                            label='Guide Star Brightness System',
                                            choices=(('Vega', 'Vega'), ('AB', 'AB'), ('Jy', 'Jy')))
    gsbrightness_band = forms.ChoiceField(required=False,
                                          initial='UC',
                                          label='Guide Star Brightness Band',
                                          choices=(('UP', 'u'), ('U', 'U'), ('B', 'B'), ('GP', 'g'), ('V', 'V'),
                                                   ('UC', 'UC'), ('RP', 'r'), ('R', 'R'), ('IP', 'i'), ('I', 'I'),
                                                   ('ZP', 'z'), ('Y', 'Y'), ('J', 'J'), ('H', 'H'), ('K', 'K'),
                                                   ('L', 'L'), ('M', 'M'), ('N', 'N'), ('Q', 'Q'), ('AP', 'AP')))
    gsprobe = forms.ChoiceField(required=False,
                                label='Guide Probe',
                                initial='OIWFS',
                                choices=(('OIWFS', 'OIWFS'),
                                         ('PWFS1', 'PWFS1'),
                                         ('PWFS2', 'PWFS2'),
                                         ('AOWFS', 'AOWFS')))  # GS probe (PWFS1/PWFS2/OIWFS/AOWFS)
    window_start = forms.CharField(required=False, widget=forms.TextInput(attrs={'type': 'date'}),
                                   label='Timing Window [Date Time]')
    window_duration = forms.IntegerField(required=False, min_value=1, label='Timing Window Duration [hr]')

    def layout(self):
        return Div(
            HTML('<big>Observation Parameters</big>'),
            HTML('<p>Select the Obsids of one or more templates. <br>'),
            HTML('Setting Ready=No will keep the new observation(s) On Hold. <br>'),
            HTML('If a value is not set, then the template default is used. <br>'),
            HTML('If setting Exptime, then provide a list of values if selecting more than one Obsid.</p>'),
            Div(
                Div(
                    'obsid',
                    css_class='col'
                ),
                Div(
                    'ready',
                    css_class='col'
                ),
                Div(
                    'notetitle',
                    css_class='col'
                ),
                css_class='form-row'
            ),
            Div(
                Div(
                    'posangle', 'brightness', 'eltype', 'group',
                    css_class='col'
                ),
                Div(
                    'exptimes', 'brightness_band', 'elmin', 'window_start',
                    css_class='col'
                ),
                Div(
                    'note', 'brightness_system', 'elmax', 'window_duration',
                    css_class='col'
                ),
                css_class='form-row'
            ),
            HTML('<big>Optional Guide Star Parameters</big>'),
            HTML('<p>If any one of Name/RA/Dec is given, then all must be.</p>'),
            Div(
                Div(
                    'gstarg', 'gsbrightness', 'gsprobe',
                    css_class='col'
                ),
                Div(
                    'gsra', 'gsbrightness_band',
                    css_class='col'
                ),
                Div(
                    'gsdec', 'gsbrightness_system',
                    css_class='col'
                ),
                css_class='form-row',
            )
        )

    def is_valid(self):
        super().is_valid()
        errors = GEMFacility.validate_observation(self.observation_payload())
        if errors:
            self.add_error(None, flatten_error_dict(self, errors))
        return not errors

    def observation_payload(self):

        def isodatetime(value):
            isostring = parse(value).isoformat()
            ii = isostring.find('T')
            date = isostring[0:ii]
            time = isostring[ii + 1:]
            return date, time

        payloads = []

        target = Target.objects.get(pk=self.cleaned_data['target_id'])
        spa = str(self.cleaned_data['posangle']).strip()

        nobs = len(self.cleaned_data['obsid'])
        if self.cleaned_data['exptimes'] != '':
            expvalues = self.cleaned_data['exptimes'].split(',')
            if len(expvalues) != nobs:
                payloads.append({"error": "If exptimes given, the number of values must equal the number of obsids "
                                          "selected."})
                return payloads

            # Convert exposure times to integers
            exptimes = []
            try:
                [exptimes.append(round(float(exp))) for exp in expvalues]
            except Exception:
                payloads.append({"error": "Problem converting string to integer."})
                return payloads

        for jj in range(nobs):
            obs = self.cleaned_data['obsid'][jj]
            ii = obs.rfind('-')
            progid = obs[0:ii]
            obsnum = obs[ii+1:]
            payload = {
                "prog": progid,
                "password": GEM_SETTINGS['api_key'][get_site(obs)],
                "email": GEM_SETTINGS['user_email'],
                "obsnum": obsnum,
                "target": target.name,
                "ra": target.ra,
                "dec": target.dec,
                "ready": self.cleaned_data['ready']
            }

            if self.cleaned_data['notetitle'] != 'Finding Chart' or self.cleaned_data['note'] != '':
                payload["noteTitle"] = self.cleaned_data['notetitle']
                payload["note"] = self.cleaned_data['note']

            if self.cleaned_data['brightness'] is not None:
                smags = str(self.cleaned_data['brightness']).strip() + '/' + \
                    self.cleaned_data['brightness_band'] + '/' + \
                    self.cleaned_data['brightness_system']
                payload["mags"] = smags

            if self.cleaned_data['exptimes'] != '':
                payload['exptime'] = exptimes[jj]

            if self.cleaned_data['group'].strip() != '':
                payload['group'] = self.cleaned_data['group'].strip()

            # timing window?
            if self.cleaned_data['window_start'].strip() != '':
                wdate, wtime = isodatetime(self.cleaned_data['window_start'])
                payload['windowDate'] = wdate
                payload['windowTime'] = wtime
                payload['windowDuration'] = str(self.cleaned_data['window_duration']).strip()

            # elevation/airmass
            if self.cleaned_data['eltype'] is not None:
                payload['elevationType'] = self.cleaned_data['eltype']
                payload['elevationMin'] = str(self.cleaned_data['elmin']).strip()
                payload['elevationMax'] = str(self.cleaned_data['elmax']).strip()

            # Guide star
            gstarg = self.cleaned_data['gstarg']
            if gstarg != '':
                gsra = self.cleaned_data['gsra']
                gsdec = self.cleaned_data['gsdec']
                if self.cleaned_data['gsbrightness'] is not None:
                    sgsmag = str(self.cleaned_data['gsbrightness']).strip() + '/' + \
                             self.cleaned_data['gsbrightness_band'] + '/' + \
                             self.cleaned_data['gsbrightness_system']

            if gstarg != '':
                payload['gstarget'] = gstarg
                payload['gsra'] = gsra
                payload['gsdec'] = gsdec
                payload['gsmags'] = sgsmag
                payload['gsprobe'] = self.cleaned_data['gsprobe']

            payload['posangle'] = spa

            payloads.append(payload)

        return payloads


class GEMFacility(BaseRoboticObservationFacility):
    """
    The ``GEMFacility`` is the interface to the Gemini Telescope. For information regarding Gemini observing and the
    available parameters, please see https://www.gemini.edu/observing/start-here
    """

    name = 'GEM'
    observation_types = [('OBSERVATION', 'Gemini Observation')]

    def get_form(self, observation_type):
        return GEMObservationForm

    @classmethod
    def submit_observation(clz, observation_payload):
        obsids = []
        for payload in observation_payload:
            response = make_request(
                'POST',
                PORTAL_URL[get_site(payload['prog'])] + '/too',
                verify=False,
                params=payload
            )
            # Return just observation number
            obsid = response.text.split('-')
            obsids.append(obsid[-1])
        return obsids

    @classmethod
    def validate_observation(clz, observation_payload):
        # Gemini doesn't have an API for validation, but run some checks
        errors = {}
        if 'elevationType' in observation_payload[0].keys():
            if observation_payload[0]['elevationType'] == 'airmass':
                if float(observation_payload[0]['elevationMin']) < 1.0:
                    errors['elevationMin'] = 'Airmass must be >= 1.0'
                if float(observation_payload[0]['elevationMax']) > 2.5:
                    errors['elevationMax'] = 'Airmass must be <= 2.5'

        for payload in observation_payload:
            if 'error' in payload.keys():
                errors['exptimes'] = payload['error']
            if 'exptime' in payload.keys():
                if payload['exptime'] <= 0:
                    errors['exptimes'] = 'Exposure time must be >= 1'
                if payload['exptime'] > 1200:
                    errors['exptimes'] = 'Exposure time must be <= 1200'

        return errors

    @classmethod
    def get_observation_url(clz, observation_id):
        # return PORTAL_URL + '/requests/' + observation_id
        return ''

    def get_start_end_keywords(self):
        return ('window_start', 'window_end')

    @classmethod
    def get_terminal_observing_states(clz):
        return TERMINAL_OBSERVING_STATES

    @classmethod
    def get_observing_sites(clz):
        return SITES

    @classmethod
    def get_observation_status(clz, observation_id):
        return {'state': '', 'scheduled_start': None, 'scheduled_end': None}

    @classmethod
    def _portal_headers(clz):
        return {}

    @classmethod
    def _archive_headers(clz):
        return {}

    @classmethod
    def data_products(clz, observation_record, product_id=None):
        return []

    @classmethod
    def _archive_frames(clz, observation_id, product_id=None):
        return []
