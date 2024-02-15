import requests
from urllib.parse import urlencode

from crispy_forms.layout import HTML, Layout, Div, Fieldset, Row, Column
from django import forms
from django.conf import settings

from tom_alerts.alerts import GenericQueryForm, GenericAlert, GenericBroker
from tom_targets.models import Target

LASAIR_URL = 'https://lasair-ztf.lsst.ac.uk'


class LasairBrokerForm(GenericQueryForm):
    cone_ra = forms.CharField(required=False, label='RA', help_text='Object RA (Decimal Degrees)',
                              widget=forms.TextInput(attrs={'placeholder': '1.2345'}))
    cone_dec = forms.CharField(required=False, label='Dec', help_text='Object Dec (Decimal Degrees)',
                               widget=forms.TextInput(attrs={'placeholder': '1.2345'}))
    cone_radius = forms.CharField(required=False, label='Radius', help_text='Search Radius (Arcsec)', initial='10',
                                  widget=forms.TextInput(attrs={'placeholder': '10'}))
    sqlquery = forms.CharField(required=False, label='SQL Query the "Objects" table.',
                               help_text='The "WHERE" criteria to restrict which objects are returned. '
                                         '(i.e. gmag < 12.0)')

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.helper.layout = Layout(
            HTML('''
                    <p>
                    Please see the <a href="https://lasair.readthedocs.io/en/main/core_functions/rest-api.html#"
                    target="_blank">Lasair website</a> for more detailed instructions on querying the broker.
                '''),
            self.common_layout,
            Fieldset(
                'Cone Search',
                Row(
                    Column('cone_ra', css_class='form-group col-md-4 mb-0'),
                    Column('cone_dec', css_class='form-group col-md-4 mb-0'),
                    Column('cone_radius', css_class='form-group col-md-4 mb-0'),
                    css_class='form-row'
                ),
                HTML("""<br>
                    <h4>SQL Query Search</h4>
                    """),

                Div('sqlquery')
            )
        )

    def clean(self):
        cleaned_data = super().clean()

        # Ensure that either cone search or sqlquery are populated
        if not ((cleaned_data['cone_ra'] and cleaned_data['cone_dec']) or cleaned_data['sqlquery']):
            raise forms.ValidationError('Either RA/Dec or Freeform SQL Query must be populated.')

        return cleaned_data


def get_lasair_object(obj):
    """Parse lasair object table"""
    objectid = obj['objectId']
    jdmax = obj['candidates'][0]['mjd']
    ra = obj['objectData']['ramean']
    dec = obj['objectData']['decmean']
    glon = obj['objectData']['glonmean']
    glat = obj['objectData']['glatmean']
    magpsf = obj['candidates'][0]['magpsf']
    return {
        'alert_id': objectid,
        'timestamp': jdmax,
        'ra': ra,
        'dec': dec,
        'galactic_lng': glon,
        'galactic_lat': glat,
        'mag': magpsf
    }


class LasairBroker(GenericBroker):
    """
    The ``LasairBroker`` is the interface to the Lasair alert broker.

    To include the ``LasairBroker`` in your TOM, add the broker module location to your `TOM_ALERT_CLASSES` list in
    your ``settings.py``:

    .. code-block:: python

        TOM_ALERT_CLASSES = [
            'tom_alerts.brokers.lasair.LasairBroker',
            ...
        ]

    Requires a `LASAIR['api_key']` value in the `BROKERS` dictionary in your settings.py.

    Create an account at https://lasair-ztf.lsst.ac.uk/, log in, and check your profile page for your API token.
    Add the api key to your settings.py file as follows, storing the token in an environment variable for security:

    .. code-block:: python

        BROKERS = {
            'LASAIR': {
                'api_key': os.getenv('LASAIR_API_KEY', ''),
            },
            ...
        }

    For information regarding the query format for
    Lasair, please see https://lasair.readthedocs.io/en/main/core_functions/rest-api.html#.
    """

    name = 'Lasair'
    form = LasairBrokerForm

    def fetch_alerts(self, parameters):
        alerts = []
        broker_feedback = ''
        object_ids = ''
        try:
            token = settings.BROKERS['LASAIR']['api_key']
        except KeyError:
            try:
                token = settings.LASAIR_TOKEN
            except AttributeError:
                broker_feedback += "Requires a `api_key` in settings.BROKERS['LASAIR']. Log in or create an" \
                                   " account at https://lasair-ztf.lsst.ac.uk/ to acquire an API token."
                return iter(alerts), broker_feedback

        # Check for Cone Search
        if 'cone_ra' in parameters and len(parameters['cone_ra'].strip()) > 0 and\
                'cone_dec' in parameters and len(parameters['cone_dec'].strip()) > 0:

            cone_query = {'ra': parameters['cone_ra'].strip(),
                          'dec': parameters['cone_dec'].strip(),
                          'radius': parameters['cone_radius'].strip(),  # defaults to 10"
                          'requestType': 'all'  # Return all objects within radius
                          }
            parsed_cone_query = urlencode(cone_query)

            # Query LASAIR Cone Search API
            cone_response = requests.get(
                LASAIR_URL + '/api/cone/?' + parsed_cone_query + f'&token={token}&format=json'
            )
            search_results = cone_response.json()
            # Successful Search ~ [{'object': 'ZTF19abuaekk', 'separation': 205.06135003141878},...]
            # Unsuccessful Search ~ {'error': 'No object found ...'}
            try:
                # Provide comma separated string of Object IDs matching search criteria
                object_ids = ','.join([result['object'] for result in search_results])
            except TypeError:
                for key in search_results:
                    broker_feedback += f'{key}:{search_results[key]}'

        # Check for SQL Condition Query
        elif 'sqlquery' in parameters and len(parameters['sqlquery'].strip()) > 0:
            sql_query = {'selected': 'objectId',  # The only parameter we need returned is the objectId
                         'tables': 'objects',  # The only table we need to search is the objects table
                         'conditions': parameters['sqlquery'].strip(),
                         'limit': '1000'  # limit number of returned objects to 1000
                         }
            parsed_sql_query = urlencode(sql_query)

            # Query LASAIR SQLQuery API
            query_response = requests.get(
                LASAIR_URL + '/api/query/?' + parsed_sql_query + f'&token={token}&format=json'
            )

            search_results = query_response.json()
            # Successful Search ~ [{'objectId': 'ZTF18aagzzzz'},...]
            # Unsuccessful Search ~ []
            try:
                # Provide comma separated string of Object IDs matching search criteria
                object_ids = ','.join([result['objectId'] for result in search_results])
            except TypeError:
                for key in search_results:
                    broker_feedback += f'{key}:{search_results[key]}'

            # Supply feedback for empty results
            if not object_ids and not broker_feedback:
                broker_feedback += f"No objects found with conditions: {sql_query['conditions']}"
        else:
            return iter(alerts), broker_feedback

        if object_ids:
            # Query LASAIR object API
            obj_response = requests.get(
                LASAIR_URL + '/api/objects/' + f'?objectIds={object_ids}&token={token}&format=json'
            )
            obj_results = obj_response.json()
            # Successful Search ~ [{'objectId': 'ZTF19abuaekk', 'objectData': {...}},...]

            for obj in obj_results:
                alerts.append(get_lasair_object(obj))
        return iter(alerts), broker_feedback

    def fetch_alert(self, alert_id):
        url = LASAIR_URL + '/object/' + alert_id + '/json/'
        response = requests.get(url)
        response.raise_for_status()
        parsed = response.json()
        return parsed

    def process_reduced_data(self, target, alert=None):
        pass

    def to_generic_alert(self, alert):
        return GenericAlert(
            url=LASAIR_URL + '/object/' + alert['alert_id'],
            id=alert['alert_id'],
            name=alert['alert_id'],
            ra=alert['ra'],
            dec=alert['dec'],
            timestamp=alert['timestamp'],
            mag=alert['mag'],
            score=1,  # dunno what this means ..?
        )

    def to_target(self, alert):
        for c in alert['candidates']:
            if 'candid' in c:
                break
        return Target.objects.create(
            name=alert.get('objectId'),
            type='SIDEREAL',
            ra=alert['objectData']['ramean'],
            dec=alert['objectData']['decmean'],
            galactic_lng=alert['objectData']['glonmean'],
            galactic_lat=alert['objectData']['glatmean'],
        )
