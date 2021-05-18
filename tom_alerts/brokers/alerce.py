import logging
import requests
from urllib.parse import urlencode

from astropy.time import Time, TimezoneInfo
from crispy_forms.layout import Column, Fieldset, Layout, Row
from django import forms
from django.core.cache import cache

from tom_alerts.alerts import GenericAlert, GenericBroker, GenericQueryForm
from tom_targets.models import Target

logger = logging.getLogger(__name__)

ALERCE_URL = 'https://alerce.online'
ALERCE_SEARCH_URL = 'https://api.alerce.online/ztf/v1'
ALERCE_CLASSES_URL = f'{ALERCE_SEARCH_URL}/classifiers'

SORT_CHOICES = [('None', 'None'),
                ('oid', 'Object ID'),
                ('probability', 'Classifier Probability'),
                ('ndet', 'Number of Detections'),
                ('firstmjd', 'First Detection'),
                ('lastmjd', 'Last Detection'),
                ('meanra', 'Mean Right Ascension'),
                ('meandec', 'Mean Declination')]

SORT_ORDER = [('None', 'None'),
              ('ASC', 'Ascending'),
              ('DESC', 'Descending')]


class ALeRCEQueryForm(GenericQueryForm):

    oid = forms.CharField(
        required=False,
        label='Object ID',
    )
    ndet = forms.IntegerField(
        required=False,
        label='Detections Lower',
        widget=forms.TextInput(attrs={'placeholder': 'Min number of detections'})
    )
    ranking = forms.IntegerField(
        required=False,
        label='Ranking',
        widget=forms.TextInput(attrs={'placeholder': 'Class ordering by probability'})
    )
    lc_classifier = forms.ChoiceField(
        required=False,
        label='Light Curve Class',
        choices=[],  # Choices are populated dynamically in the constructor
    )
    p_lc_classifier = forms.FloatField(
        required=False,
        label='Light Curve Classifier Probability'
    )
    stamp_classifier = forms.ChoiceField(
        required=False,
        label='Stamp Class',
        choices=[],  # Choices are populated dynamically in the constructor
    )
    p_stamp_classifier = forms.FloatField(
        required=False,
        label='Stamp Classifier Probability'
    )
    ra = forms.FloatField(
        required=False,
        label='RA',
        widget=forms.TextInput(attrs={'placeholder': 'RA (Degrees)'})
    )
    dec = forms.FloatField(
        required=False,
        label='Dec',
        widget=forms.TextInput(attrs={'placeholder': 'Dec (Degrees)'})
    )
    radius = forms.IntegerField(
        required=False,
        label='Search Radius',
        widget=forms.TextInput(attrs={'placeholder': 'Radius (Arcseconds)'})
    )
    firstmjd__gt = forms.FloatField(
        required=False,
        label='Min date of first detection ',
        widget=forms.TextInput(attrs={'placeholder': 'Date (MJD)'}),
        min_value=0.0
    )
    firstmjd__lt = forms.FloatField(
        required=False,
        label='Max date of first detection ',
        widget=forms.TextInput(attrs={'placeholder': 'Date (MJD)'}),
        min_value=0.0
    )
    lastmjd__gt = forms.FloatField(
        required=False,
        label='Min date of last detection',
        widget=forms.TextInput(attrs={'placeholder': 'Date (MJD)'}),
        min_value=0.0
    )
    lastmjd__lt = forms.FloatField(
        required=False,
        label='Max date of last detection',
        widget=forms.TextInput(attrs={'placeholder': 'Date (MJD)'}),
        min_value=0.0
    )
    order_by = forms.ChoiceField(
        choices=SORT_CHOICES,
        required=False,
        label='Sort By'
    )
    order_mode = forms.ChoiceField(
        choices=SORT_ORDER,
        required=False,
        label='Sort Order'
    )
    max_pages = forms.TypedChoiceField(
        choices=[(1, 1), (5, 5), (10, 10), (20, 20)],
        required=False,
        coerce=int,
        label='Maximum pages to retrieve'
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.fields['lc_classifier'].choices = self._get_light_curve_classifier_choices()
        self.fields['stamp_classifier'].choices = self._get_stamp_classifier_choices()

        self.helper.layout = Layout(
            self.common_layout,
            'oid',
            Fieldset(
                'Classification Filters',
                Row(
                    Column('lc_classifier'),
                    Column('p_lc_classifier')
                ),
                Row(
                    Column('stamp_classifier'),
                    Column('p_stamp_classifier')
                )
            ),
            Fieldset(
                'Location Filters',
                Row(
                    Column('ra'),
                    Column('dec'),
                    Column('radius'),
                )
            ),
            Fieldset(
                'Time Filters',
                Row(
                    Column('firstmjd__gt'),
                    Column('firstmjd__lt'),
                ),
                Row(
                    Column('lastmjd__gt'),
                    Column('lastmjd__lt'),
                )
            ),
            Fieldset(
                'Other Filters',
                Row(
                    Column('ranking'),
                    Column('ndet')
                )
            ),
            Fieldset(
                'General Parameters',
                Row(
                    Column('order_by'),
                    Column('order_mode'),
                ),
                Row(
                    Column('max_pages')
                )
            ),
        )

    @staticmethod
    def _get_classifiers():
        cached_classifiers = cache.get('alerce_classifiers')

        if not cached_classifiers:
            response = requests.get(ALERCE_CLASSES_URL)
            response.raise_for_status()
            cached_classifiers = response.json()

        return cached_classifiers

    @staticmethod
    def _get_light_curve_classifier_choices():
        light_curve_classifiers = []
        for classifier in ALeRCEQueryForm._get_classifiers():
            if (any(x in classifier['classifier_name'] for x in ['transient', 'stochastic', 'periodic'])):
                classifier_name = classifier['classifier_name'].split('_')[-1]
                light_curve_classifiers += [(c, f'{c} - {classifier_name}') for c in classifier['classes']]

        return [(None, '')] + light_curve_classifiers

    @staticmethod
    def _get_stamp_classifier_choices():
        version = '0.0.0'
        stamp_classifiers = []

        for classifier in ALeRCEQueryForm._get_classifiers():
            if classifier['classifier_name'] == 'stamp_classifier':
                new_version = classifier['classifier_version'].split('_')[-1]
                if new_version > version:
                    stamp_classifiers = [(c, c) for c in classifier['classes']]

        return [(None, '')] + stamp_classifiers

    def clean_max_pages(self):
        max_pages = self.cleaned_data['max_pages']
        if not max_pages:
            max_pages = 1
        return max_pages

    def clean(self):
        cleaned_data = super().clean()

        # Ensure that all cone search fields are present
        if (any(cleaned_data[k] for k in ['ra', 'dec', 'radius'])
                and not all(cleaned_data[k] for k in ['ra', 'dec', 'radius'])):
            raise forms.ValidationError('All of RA, Dec, and Search Radius must be included to execute a cone search.')

        # Ensure that only one classification set is filled in
        if (any(cleaned_data.get(k) for k in ['lc_classifier', 'p_lc_classifier'])
                and any(cleaned_data.get(k) for k in ['stamp_classifier', 'p_stamp_classifier'])):
            raise forms.ValidationError('Only one of either light curve or stamp classification may be used as a '
                                        'filter.')

        return cleaned_data


class ALeRCEBroker(GenericBroker):
    name = 'ALeRCE'
    form = ALeRCEQueryForm

    def _clean_classifier_parameters(self, parameters):
        classifier_parameters = []
        class_type = ''
        if parameters['stamp_classifier']:
            class_type = 'stamp_classifier'
        elif parameters['lc_classifier']:
            class_type = 'lc_classifier'

        if class_type:
            classifier_parameters.append(('classifier', class_type))
        if class_type in parameters and parameters[class_type] is not None:
            classifier_parameters.append(('class', parameters[class_type]))
        if f'p_{class_type}' in parameters and parameters[f'p_{class_type}'] is not None:
            classifier_parameters.append(('probability', parameters[f'p_{class_type}']))

        return classifier_parameters

    def _clean_coordinate_parameters(self, parameters):
        if all([parameters['ra'], parameters['dec'], parameters['radius']]):
            return [
                ('ra', parameters['ra']),
                ('dec', parameters['dec']),
                ('radius', parameters['radius'])
            ]
        else:
            return []

    def _clean_date_parameters(self, parameters):
        dates = []

        dates += [('firstmjd', v) for k, v in parameters.items() if 'firstmjd' in k and v]
        dates += [('lastmjd', v) for k, v in parameters.items() if 'lastmjd' in k and v]

        return dates

    def _clean_parameters(self, parameters):
        payload = [
            (k, v) for k, v in parameters.items() if k in ['oid', 'ndet', 'ranking', 'order_by', 'order_mode'] and v
        ]

        payload += [
            ('page', parameters.get('page', 1)),
            ('page_size', 20),
        ]

        payload += self._clean_classifier_parameters(parameters)

        payload += self._clean_coordinate_parameters(parameters)

        payload += self._clean_date_parameters(parameters)

        return payload

    def _request_alerts(self, parameters):
        payload = self._clean_parameters(parameters)
        logger.log(msg=f'Fetching alerts from ALeRCE with payload {payload}', level=logging.INFO)
        args = urlencode(self._clean_parameters(parameters))
        response = requests.get(f'{ALERCE_SEARCH_URL}/objects/?count=false&{args}')
        response.raise_for_status()
        return response.json()

    def fetch_alerts(self, parameters):
        response = self._request_alerts(parameters)
        alerts = response['items']
        if len(alerts) > 0 and response['page'] < parameters.get('max_pages', 1):
            parameters['page'] = response.get('page') + 1
            alerts += self.fetch_alerts(parameters)
        return iter(alerts)

    def fetch_alert(self, id):
        """
        The response for a single alert is as follows:

        {
            'oid':'ZTF20acnsdjd',
            ...
            'firstmjd':59149.1119328998,
            ...
        }
        """
        response = requests.get(f'{ALERCE_SEARCH_URL}/objects/{id}')
        response.raise_for_status()
        return response.json()

    def to_target(self, alert):
        return Target.objects.create(
            name=alert['oid'],
            type='SIDEREAL',
            ra=alert['meanra'],
            dec=alert['meandec']
        )

    # TODO: the generic alert is clearly not sufficient for ALeRCE's classifications
    def to_generic_alert(self, alert):
        if alert['lastmjd']:
            timestamp = Time(alert['lastmjd'], format='mjd', scale='utc').to_datetime(timezone=TimezoneInfo())
        else:
            timestamp = ''
        url = f'{ALERCE_URL}/object/{alert["oid"]}'

        mag = None  # mag is no longer returned in the object list

        score = alert['probability']

        return GenericAlert(
            timestamp=timestamp,
            url=url,
            id=alert['oid'],
            name=alert['oid'],
            ra=alert['meanra'],
            dec=alert['meandec'],
            mag=mag,
            score=score
        )
