import requests
from urllib.parse import urlencode

from crispy_forms.layout import Fieldset, HTML, Layout
from django import forms
from django.conf import settings

from tom_alerts.alerts import GenericQueryForm, GenericAlert, GenericBroker
from tom_targets.models import Target

LASAIR_URL = 'https://lasair-ztf.lsst.ac.uk'


class LasairBrokerForm(GenericQueryForm):
    cone = forms.CharField(required=False, label='Object Cone Search', help_text='Object RA and Dec')
    sqlquery = forms.CharField(required=False, label='Freeform SQL query', help_text='SQL query')

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.helper.layout = Layout(
            HTML('''
                <p>
                Please see the <a href="https://lasair.roe.ac.uk/objlist/">Lasair website</a> for more detailed
                instructions on querying the broker.
            '''),
            self.common_layout,
            Fieldset(
                None,
                'cone',
                'sqlquery'
            ),
        )

    def clean(self):
        cleaned_data = super().clean()

        # Ensure that either cone search or sqlquery are populated
        if not (cleaned_data['cone'] or cleaned_data['sqlquery']):
            raise forms.ValidationError('One of either Object Cone Search or Freeform SQL Query must be populated.')

        return cleaned_data


def get_lasair_object(obj):
    objectId = obj['objectId']
    jdmax = obj['candidates'][0]['mjd']
    ra = obj['objectData']['ramean']
    dec = obj['objectData']['decmean']
    glon = obj['objectData']['glonmean']
    glat = obj['objectData']['glatmean']
    magpsf = obj['candidates'][0]['magpsf']
    return {
        'alert_id': objectId,
        'timestamp': jdmax,
        'ra': ra,
        'dec': dec,
        'galactic_lng': glon,
        'galactic_lat': glat,
        'mag': magpsf
    }


class LasairBroker(GenericBroker):
    """
    The ``LasairBroker`` is the interface to the Lasair alert broker. For information regarding the query format for
    Lasair, please see https://lasair.roe.ac.uk/objlist/.
    """

    name = 'Lasair'
    form = LasairBrokerForm

    def fetch_alerts(self, parameters):
        token = settings.LASAIR_TOKEN
        alerts = []
        messages = ''
        object_ids = ''
        if 'cone' in parameters and len(parameters['cone'].strip()) > 0:

            cone_query = {'ra': (parameters['cone'].strip().split(','))[0],
                          'dec': (parameters['cone'].strip().split(','))[1],
                          'radius': 200,
                          'requestType': 'all'}
            parsed_cone_query = urlencode(cone_query)

            cone_response = requests.get(
                LASAIR_URL + '/api/cone/?' + parsed_cone_query + f'&token={token}&format=json'
            )
            search_results = cone_response.json()
            try:
                object_ids = ','.join([result['object'] for result in search_results])
            except TypeError:
                for key in search_results:
                    messages += f'{key}:{search_results[key]}'

        # note: the sql SELECT must include objectId
        elif 'sqlquery' in parameters and len(parameters['sqlquery'].strip()) > 0:
            sql_query = {'selected': 'objectId',
                         'tables': 'objects',
                         'conditions': 'gmag < 12.0',
                         'limit': '100'}
            parsed_sql_query = urlencode(sql_query)

            query_response = requests.get(
                LASAIR_URL + '/api/query/?' + parsed_sql_query + f'&token={token}&format=json'
            )

            search_results = query_response.json()
            try:
                object_ids = ','.join([result['objectId'] for result in search_results])
            except TypeError:
                for key in search_results:
                    messages += f'{key}:{search_results[key]}'

            if not object_ids and not messages:
                messages += f"No objects found with conditions: {sql_query['conditions']}"
        else:
            return iter(alerts), messages

        if object_ids:
            obj_response = requests.get(
                LASAIR_URL + '/api/objects/' + f'?objectIds={object_ids}&token={token}&format=json'
            )
            obj_results = obj_response.json()

            for obj in obj_results:
                alerts.append(get_lasair_object(obj))
        return iter(alerts), messages

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
