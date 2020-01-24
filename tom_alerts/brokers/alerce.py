import requests

from django import forms
from crispy_forms.layout import Layout, Div, Fieldset
from astropy.time import Time, TimezoneInfo
import datetime

from tom_alerts.alerts import GenericQueryForm, GenericBroker, GenericAlert
from tom_targets.models import Target

ALERCE_URL = 'https://alerce.online'
ALERCE_SEARCH_URL = 'https://ztf.alerce.online/query'
ALERCE_CLASSES_URL = 'https://ztf.alerce.online/get_current_classes'

SORT_CHOICES = [("nobs", "Number Of Epochs"),
                ("lastmjd", "Last Detection"),
                ("pclassrf", "Late Probability"),
                ("pclassearly", "Early Probability")]

PAGES_CHOICES = [
    (i, i) for i in [1, 5, 10, 15]
]

RECORDS_CHOICES = [
    (i, i) for i in [20, 100, 500]
]


class ALeRCEQueryForm(GenericQueryForm):

    RF_CLASSIFIERS = []
    STAMP_CLASSIFIERS = []

    nobs__gt = forms.IntegerField(
        required=False,
        label='Detections Lower',
        widget=forms.TextInput(attrs={'placeholder': 'Min number of epochs'})
    )
    nobs__lt = forms.IntegerField(
        required=False,
        label='Detections Upper',
        widget=forms.TextInput(attrs={'placeholder': 'Max number of epochs'})
    )
    classrf = forms.ChoiceField(
        required=False,
        label='Late Classifier (Random Forest)',
        choices=RF_CLASSIFIERS
    )
    pclassrf = forms.FloatField(
        required=False,
        label='Classifier Probability (Random Forest)'
    )
    classearly = forms.ChoiceField(
        required=False,
        label='Early Classifier (Stamp Classifier)',
        choices=STAMP_CLASSIFIERS
    )
    pclassearly = forms.FloatField(
        required=False,
        label='Classifier Probability (Stamp Classifier)'
    )
    ra = forms.IntegerField(
        required=False,
        label='RA',
        widget=forms.TextInput(attrs={'placeholder': 'RA (Degrees)'})
    )
    dec = forms.IntegerField(
        required=False,
        label='Dec',
        widget=forms.TextInput(attrs={'placeholder': 'Dec (Degrees)'})
    )
    sr = forms.IntegerField(
        required=False,
        label='Search Radius',
        widget=forms.TextInput(attrs={'placeholder': 'SR (Degrees)'})
    )
    mjd__gt = forms.FloatField(
        required=False,
        label='Min date of first detection ',
        widget=forms.TextInput(attrs={'placeholder': 'Date (MJD)'})
    )
    mjd__lt = forms.FloatField(
        required=False,
        label='Max date of first detection',
        widget=forms.TextInput(attrs={'placeholder': 'Date (MJD)'})
    )
    relative_mjd__gt = forms.FloatField(
        required=False,
        label='Relative date of object discovery.',
        widget=forms.TextInput(attrs={'placeholder': 'Hours'})
    )
    sort_by = forms.ChoiceField(
            choices=SORT_CHOICES,
            required=False,
            label='Sort By'
    )
    max_pages = forms.TypedChoiceField(
            choices=PAGES_CHOICES,
            required=False,
            label='Max Number of Pages'
    )
    records = forms.ChoiceField(
            choices=RECORDS_CHOICES,
            required=False,
            label='Records per page'
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        response = requests.post(ALERCE_CLASSES_URL)
        response.raise_for_status()
        parsed = response.json()

        EARLY_CHOICES = [(c["id"], c["name"]) for c in parsed["early"]]
        EARLY_CHOICES.insert(0, (None, ""))
        LATE_CHOICES = [(c["id"], c["name"]) for c in parsed["late"]]
        LATE_CHOICES.insert(0, (None, ""))

        self.fields["classearly"].choices = EARLY_CHOICES
        self.fields["classrf"].choices = LATE_CHOICES

        self.helper.layout = Layout(
            self.common_layout,
            Fieldset(
                'Number of Epochs',
                Div(
                    Div(
                        'nobs__gt',
                        css_class='col',
                    ),
                    Div(
                        'nobs__lt',
                        css_class='col',
                    ),
                    css_class="form-row",
                )
            ),
            Fieldset(
                'Classification Filters',
                Div(
                    Div(
                        'classrf',
                        'classearly',
                        css_class='col'
                    ),
                    Div(
                        'pclassrf',
                        'pclassearly',
                        css_class='col',
                    ),
                    css_class="form-row",
                )
            ),
            Fieldset(
                'Location Filters',
                Div(
                    Div(
                        'ra',
                        css_class="col"
                    ),
                    Div(
                        'dec',
                        css_class='col'
                    ),
                    Div(
                        'sr',
                        css_class='col'
                    ),
                    css_class="form-row"
                )
            ),
            Fieldset(
                'Time Filters',
                Div(
                    Fieldset(
                        "Relative time",
                        Div(
                            'relative_mjd__gt',
                            css_class='col',
                        ),
                        css_class='col'
                    ),
                    Fieldset(
                        "Absolute time",
                        Div(
                            Div(
                                'mjd__gt',
                                css_class='col',
                            ),
                            Div(
                                'mjd__lt',
                                css_class='col',
                            ),
                            css_class="form-row"
                        )
                    ),
                    css_class="form-row"
                )
            ),
            Fieldset(
                'General Parameters',
                Div(
                    Div(
                        "sort_by",
                        css_class="col"
                    ),
                    Div(
                        "records",
                        css_class="col"
                    ),
                    Div(
                        "max_pages",
                        css_class="col"
                    ),
                    css_class="form-row"
                )
            ),
        )


class ALeRCEBroker(GenericBroker):
    name = 'ALeRCE'
    form = ALeRCEQueryForm

    def _fetch_alerts_payload(self, parameters):
        payload = {
            'page': parameters.get('page', 1),
            'records_per_pages': int(parameters.get('records', 20)),
            'sortBy': parameters.get('sort_by'),
            'query_parameters': {
            }
        }
        if parameters.get('total'):
            payload['total'] = parameters.get('total')

        if any([parameters['nobs__gt'],
                parameters['nobs__lt'],
                parameters['classrf'],
                parameters['pclassrf'],
                parameters['classearly'],
                parameters['pclassearly']]):
            filters = {}
            if any([parameters['nobs__gt'],
                    parameters['nobs__lt']]):
                filters['nobs'] = {}
                if parameters['nobs__gt']:
                    filters['nobs']['min'] = parameters['nobs__gt']
                if parameters['nobs__lt']:
                    filters['nobs']['max'] = parameters['nobs__lt']
            if parameters['classrf']:
                filters['classrf'] = int(parameters['classrf'])
            if parameters['pclassrf']:
                filters['pclassrf'] = parameters['pclassrf']
            if parameters['classearly']:
                filters['classearly'] = int(parameters['classearly'])
            if parameters['pclassearly']:
                filters['pclassearly'] = parameters['pclassearly']
            payload['query_parameters']['filters'] = filters

        if all([parameters['ra'],
                parameters['dec'],
                parameters['sr']]):
            coordinates = {}
            if parameters['ra']:
                coordinates['ra'] = parameters['ra']
            if parameters['dec']:
                coordinates['dec'] = parameters['dec']
            if parameters['sr']:
                coordinates['sr'] = parameters['sr']
            payload['query_parameters']['coordinates'] = coordinates

        if any([parameters['mjd__gt'],
                parameters['mjd__lt'],
                parameters['relative_mjd__gt']]):
            dates = {'firstmjd': {}}
            if parameters['mjd__gt']:
                dates['firstmjd']['min'] = parameters['mjd__gt']
            elif parameters['relative_mjd__gt']:
                now = datetime.datetime.utcnow()
                relative = now - datetime.timedelta(hours=parameters['relative_mjd__gt'])
                relative_astro = Time(relative)
                dates['firstmjd']['min'] = relative_astro.mjd

            if parameters['mjd__lt']:
                dates['firstmjd']['max'] = parameters['mjd__lt']
            payload['query_parameters']['dates'] = dates

        return payload

    def fetch_alerts(self, parameters):
        payload = self._fetch_alerts_payload(parameters)
        response = requests.post(ALERCE_SEARCH_URL, json=payload)
        response.raise_for_status()
        parsed = response.json()
        alerts = [alert_data for alert, alert_data in parsed['result'].items()]
        if parsed['page'] < parsed['num_pages'] and parsed['page'] != int(parameters["max_pages"]):
            parameters['page'] = parameters.get('page', 1) + 1
            parameters['total'] = parsed.get('total')
            alerts += self.fetch_alerts(parameters)
        return iter(alerts)

    def fetch_alert(self, id):
        payload = {
            'query_parameters': {
                'filters': {
                    'oid': id
                }
            }
        }
        response = requests.post(ALERCE_SEARCH_URL, json=payload)
        response.raise_for_status()
        return response.json()['result'][0]

    def to_target(self, alert):
        return Target.objects.create(
            name=alert['oid'],
            type='SIDEREAL',
            ra=alert['meanra'],
            dec=alert['meandec']
        )

    def to_generic_alert(self, alert):
        if alert['lastmjd']:
            timestamp = Time(alert['lastmjd'], format='mjd', scale='utc').to_datetime(timezone=TimezoneInfo())
        else:
            timestamp = ''
        url = '{0}/{1}/{2}'.format(ALERCE_URL, 'object', alert['oid'])

        exits = (alert['mean_magpsf_g'] is None and alert['mean_magpsf_r'] is not None)
        both_exists = (alert['mean_magpsf_g'] is not None and alert['mean_magpsf_r'] is not None)
        bigger = (both_exists and (alert['mean_magpsf_r'] < alert['mean_magpsf_g'] is not None))
        is_r = any([exits, bigger])

        max_mag = alert['mean_magpsf_r'] if is_r else alert['mean_magpsf_g']

        if alert['pclassrf']:
            score = alert["pclassrf"]
        elif alert['pclassearly']:
            score = alert['pclassearly']
        else:
            score = None

        return GenericAlert(
            timestamp=timestamp,
            url=url,
            id=alert['oid'],
            name=alert['oid'],
            ra=alert['meanra'],
            dec=alert['meandec'],
            mag=max_mag,
            score=score
        )
