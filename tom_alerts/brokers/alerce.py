import logging
import requests
from urllib.parse import urlencode

from astropy.time import Time, TimezoneInfo
from crispy_forms.layout import Column, Fieldset, HTML, Layout, Row
from django import forms
from django.core.cache import cache


from tom_alerts.alerts import GenericAlert, GenericBroker, GenericQueryForm
from tom_targets.models import Target
from tom_dataproducts.models import ReducedDatum

logger = logging.getLogger(__name__)

ALERCE_URL = 'https://alerce.online'
ALERCE_SEARCH_URL = 'https://api.alerce.online/ztf/v1'
ALERCE_CLASSES_URL = f'{ALERCE_SEARCH_URL}/classifiers'

SORT_CHOICES = [(None, 'None'),
                ('oid', 'Object ID'),
                ('probability', 'Classifier Probability'),
                ('ndet', 'Number of Detections'),
                ('firstmjd', 'First Detection'),
                ('lastmjd', 'Last Detection'),
                ('deltamjd', 'Delta MJD (days)')
                ]

SORT_ORDER = [(None, 'None'),
              ('ASC', 'Ascending'),
              ('DESC', 'Descending')]
FILTERS = {1: 'g', 2: 'r', 3: 'i'}


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
        label='Light Curve Classifier Class',
        choices=[],  # Choices are populated dynamically in the constructor
    )
    p_lc_classifier = forms.FloatField(
        required=False,
        label='Light Curve Classifier Probability'
    )
    lc_classifier_top = forms.ChoiceField(
        required=False,
        label='Light Curve Classifier Top Class',
        choices=[],  # Choices are populated dynamically in the constructor
    )
    p_lc_classifier_top = forms.FloatField(
        required=False,
        label='Light Curve Classifier Top Probability'
    )
    lc_classifier_bhrf = forms.ChoiceField(
        required=False,
        label='Light Curve Classifier BHRF Forced Phot Class',
        choices=[],  # Choices are populated dynamically in the constructor
    )
    p_lc_classifier_bhrf = forms.FloatField(
        required=False,
        label='Light Curve Classifier BHRF Forced Phot Probability'
    )
    lc_classifier_bhrf_top = forms.ChoiceField(
        required=False,
        label='Light Curve Classifier BHRF Forced Phot Top Class',
        choices=[],  # Choices are populated dynamically in the constructor
    )
    p_lc_classifier_bhrf_top = forms.FloatField(
        required=False,
        label='Light Curve Classifier BHRF Forced Phot Top Probability'
    )
    lc_classifier_atat = forms.ChoiceField(
        required=False,
        label='Light Curve Classifier ATAT Forced Phot Beta Class',
        choices=[],  # Choices are populated dynamically in the constructor
    )
    p_lc_classifier_atat = forms.FloatField(
        required=False,
        label='Light Curve Classifier ATAT Forced Phot Beta Probability'
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
    stamp_classifier_beta = forms.ChoiceField(
        required=False,
        label='Stamp Classifier 2025 Beta Class',
        choices=[],  # Choices are populated dynamically in the constructor
    )
    p_stamp_classifier_beta = forms.FloatField(
        required=False,
        label='Stamp Classifier 2025 Beta Probability'
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
        self.fields['lc_classifier_top'].choices = self._get_light_curve_classifier_top_choices()
        self.fields['lc_classifier_bhrf'].choices = self._get_light_curve_classifier_bhrf_choices()
        self.fields['lc_classifier_bhrf_top'].choices = self._get_light_curve_classifier_bhrf_top_choices()
        self.fields['lc_classifier_atat'].choices = self._get_light_curve_classifier_atat_choices()
        self.fields['stamp_classifier'].choices = self._get_stamp_classifier_choices()
        self.fields['stamp_classifier_beta'].choices = self._get_stamp_classifier_beta_choices()

        self.helper.layout = Layout(
            HTML('''
                <p>
                Please see the <a href="http://alerce.science/" target="_blank">ALeRCE homepage</a> for information
                about the ALeRCE filters.
            '''),
            self.common_layout,
            'oid',
            Fieldset(
                'Classification Filters',
                Row(
                    Column('lc_classifier'),
                    Column('p_lc_classifier')
                ),
                Row(
                    Column('lc_classifier_top'),
                    Column('p_lc_classifier_top')
                ),
                Row(
                    Column('lc_classifier_bhrf'),
                    Column('p_lc_classifier_bhrf')
                ),
                Row(
                    Column('lc_classifier_bhrf_top'),
                    Column('p_lc_classifier_bhrf_top')
                ),
                Row(
                    Column('lc_classifier_atat'),
                    Column('p_lc_classifier_atat')
                ),
                Row(
                    Column('stamp_classifier'),
                    Column('p_stamp_classifier')
                ),
                Row(
                    Column('stamp_classifier_beta'),
                    Column('p_stamp_classifier_beta')
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
        version = '1.0.0'
        current_version = version

        # Grab all classifiers available in ALeRCE
        all_classifiers = ALeRCEQueryForm._get_classifiers()

        for classifier in all_classifiers:
            if classifier['classifier_name'] == 'lc_classifier':
                new_version = classifier['classifier_version'].split('_')[-1]
                if new_version > version:
                    light_curve_classifiers = [(c, c) for c in classifier['classes']]
                    current_version = new_version

        if current_version == version:
            for classifier in all_classifiers:
                split_class = classifier['classifier_name'].split('_')
                if len(split_class) == 3 and split_class[0] == 'lc' and split_class[2] != 'top':
                    subclass = split_class[2].capitalize()
                    light_curve_classifiers += [(c, f'{subclass} - {c}') for c in classifier['classes']]

        return [(None, '')] + light_curve_classifiers

    @staticmethod
    def _get_light_curve_classifier_top_choices():
        light_curve_classifiers = []
        version = '1.0.0'

        # Grab all classifiers available in ALeRCE
        all_classifiers = ALeRCEQueryForm._get_classifiers()

        for classifier in all_classifiers:
            if classifier['classifier_name'] == 'lc_classifier_top':
                new_version = classifier['classifier_version'].split('_')[-1]
                if new_version > version:
                    light_curve_classifiers = [(c, c) for c in classifier['classes']]
                else:
                    light_curve_classifiers = [(c, c) for c in classifier['classes']]

        return [(None, '')] + light_curve_classifiers

    @staticmethod
    def _get_light_curve_classifier_bhrf_choices():
        light_curve_classifiers = []
        version = '2.1.0'
        current_version = version

        # Grab all classifiers available in ALeRCE
        all_classifiers = ALeRCEQueryForm._get_classifiers()

        for classifier in all_classifiers:
            if classifier['classifier_name'] == 'lc_classifier_BHRF_forced_phot':
                new_version = classifier['classifier_version'].split('_')[-1]
                if new_version > version:
                    light_curve_classifiers = [(c, c) for c in classifier['classes']]
                    current_version = new_version

        if current_version == version:
            for classifier in all_classifiers:
                split_class = classifier['classifier_name'].split('_')
                if len(split_class) == 3 and split_class[0] == 'lc' and split_class[2] != 'top':
                    subclass = split_class[2].capitalize()
                    light_curve_classifiers += [(c, f'{subclass} - {c}') for c in classifier['classes']]

            return [(None, '')] + light_curve_classifiers

    @staticmethod
    def _get_light_curve_classifier_bhrf_top_choices():
        light_curve_classifiers = []
        version = '1.0.0'

        # Grab all classifiers available in ALeRCE
        all_classifiers = ALeRCEQueryForm._get_classifiers()

        for classifier in all_classifiers:
            if classifier['classifier_name'] == 'lc_classifier_BHRF_forced_phot_top':
                new_version = classifier['classifier_version'].split('_')[-1]
                if new_version > version:
                    light_curve_classifiers = [(c, c) for c in classifier['classes']]
                else:
                    light_curve_classifiers = [(c, c) for c in classifier['classes']]

        return [(None, '')] + light_curve_classifiers

    @staticmethod
    def _get_light_curve_classifier_atat_choices():
        version = 'beta'
        light_curve_classifiers = []
        for classifier in ALeRCEQueryForm._get_classifiers():
            if classifier['classifier_name'] == 'LC_classifier_ATAT_forced_phot(beta)':
                new_version = classifier['classifier_version'].split('_')[-1]
                if new_version > version:
                    light_curve_classifiers = [(c, c) for c in classifier['classes']]
                else:
                    light_curve_classifiers = [(c, c) for c in classifier['classes']]

        return [(None, '')] + light_curve_classifiers

    @staticmethod
    def _get_stamp_classifier_choices():
        version = '1.0.4'
        stamp_classifiers = []

        for classifier in ALeRCEQueryForm._get_classifiers():
            if classifier['classifier_name'] == 'stamp_classifier':
                new_version = classifier['classifier_version'].split('_')[-1]
                if new_version > version:
                    stamp_classifiers = [(c, c) for c in classifier['classes']]
                else:
                    stamp_classifiers = [(c, c) for c in classifier['classes']]

        return [(None, '')] + stamp_classifiers

    @staticmethod
    def _get_stamp_classifier_beta_choices():
        version = 'beta'
        stamp_classifiers = []

        for classifier in ALeRCEQueryForm._get_classifiers():
            if classifier['classifier_name'] == 'stamp_classifier_2025_beta':
                new_version = classifier['classifier_version'].split('_')[-1]
                if new_version > version:
                    stamp_classifiers = [(c, c) for c in classifier['classes']]
                else:
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
    """
    The ``ALeRCEBroker`` is the interface to the ALeRCE alert broker.

    To include the ``ALeRCEBroker`` in your TOM, add the broker module location to your `TOM_ALERT_CLASSES` list in
    your ``settings.py``:

    .. code-block:: python

        TOM_ALERT_CLASSES = [
            'tom_alerts.brokers.alerce.ALeRCEBroker',
            ...
        ]

    For information regarding the ALeRCE objects
    and classification, please see http://alerce.science.
    """

    name = 'ALeRCE'
    form = ALeRCEQueryForm

    def _clean_classifier_parameters(self, parameters):
        """
        This method returns a parameter list for a given classifier with a
        cleaned up version of the ALeRCE classifier names.
        The function finds the ALeRCE classifier name (predefined here) and
        matches it to the TOM Toolkit ALeRCE broker classifier name. Then it
        appends the classifier_parameter list with the parameters specified in
        the TOM Toolkit ALeRCE broker query definition.

        List of available classifiers can be seen here: https://api.alerce.online/ztf/v1/classifiers/

        :param parameters:
        :return: classifier parameters tuple that holds strings with cleaned up versions of
        available classifiers.
        """

        classifier_parameters = []
        class_type = ''

        if parameters['stamp_classifier']:
            class_type = 'stamp_classifier'
        elif parameters.get('stamp_classifier_beta'):
            class_type = 'stamp_classifier_2025_beta'
        elif parameters['lc_classifier']:
            class_type = 'lc_classifier'
        elif parameters.get('lc_classifier_top'):
            class_type = 'lc_classifier_top'
        elif parameters.get('lc_classifier_bhrf'):
            class_type = 'lc_classifier_BHRF_forced_phot'
        elif parameters.get('lc_classifier_bhrf_top'):
            class_type = 'lc_classifier_BHRF_forced_phot_top'
        elif parameters.get('lc_classifier_atat'):
            class_type = 'LC_classifier_ATAT_forced_phot(beta)'

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
        args = urlencode(payload)
        response = requests.get(f'{ALERCE_SEARCH_URL}/objects/?count=false&{args}')
        response.raise_for_status()
        return response.json()

    def fetch_alerts(self, parameters):
        """
        Loop through pages of ALeRCE alerts until we reach the maximum pages requested.
        This simply concatenates all alerts from n pages into a single iterable to be returned.
        """
        response = self._request_alerts(parameters)
        alerts = response['items']
        broker_feedback = ''
        current_page = parameters.get('page', 1)
        if len(alerts) > 0 and current_page < parameters.get('max_pages', 1):
            # make new request for the next page. (by recursion)
            parameters['page'] = current_page + 1
            alerts += self.fetch_alerts(parameters)[0]
        # Bottom out of recursion and return accumulated alerts
        return iter(alerts), broker_feedback

    def fetch_alert(self, alert_id):
        """
        The response for a single alert is as follows:

        .. code-block:: python

            {
                'oid':'ZTF20acnsdjd',
                ...
                'firstmjd':59149.1119328998,
                ...
            }

        """
        response = requests.get(f'{ALERCE_SEARCH_URL}/objects/{alert_id}')
        response.raise_for_status()
        return response.json()

    def fetch_lightcurve(self, oid):
        response = requests.get(f'{ALERCE_SEARCH_URL}/objects/{oid}/lightcurve')
        response.raise_for_status()
        return response.json()

    def process_reduced_data(self, target, alert=None):
        oid = target.name
        lightcurve = self.fetch_lightcurve(oid)

        for detection in lightcurve['detections']:
            mjd = Time(detection['mjd'], format='mjd', scale='utc')
            value = {
                'filter': FILTERS[detection['fid']],
                'magnitude': detection['diffmaglim'],
                'error': detection['sigmapsf'],
                'telescope': 'ZTF',
            }
            ReducedDatum.objects.get_or_create(
                timestamp=mjd.to_datetime(TimezoneInfo()),
                value=value,
                source_name=self.name,
                source_location=oid,
                data_type='photometry',
                target=target
            )

        for non_detection in lightcurve['non_detections']:
            mjd = Time(non_detection['mjd'], format='mjd', scale='utc')
            value = {
                'filter': FILTERS[non_detection['fid']],
                'limit': non_detection['diffmaglim'],
                'telescope': 'ZTF',
            }
            ReducedDatum.objects.get_or_create(
                timestamp=mjd.to_datetime(TimezoneInfo()),
                value=value,
                source_name=self.name,
                source_location=oid,
                data_type='photometry',
                target=target
            )

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
