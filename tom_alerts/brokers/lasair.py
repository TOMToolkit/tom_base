import requests

from crispy_forms.layout import Fieldset, HTML, Layout
from django import forms

from tom_alerts.alerts import GenericQueryForm, GenericAlert, GenericBroker
from tom_targets.models import Target

LASAIR_URL = 'https://lasair.roe.ac.uk'


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


def get_lasair_object(objectId):
    url = LASAIR_URL + '/object/' + objectId + '/json/'
    response = requests.get(url)
    obj = response.json()
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
        print(parameters)
        if 'cone' in parameters and len(parameters['cone'].strip()) > 0:
            response = requests.post(
                LASAIR_URL + '/conesearch/',
                data={'cone': parameters['cone'], 'json': 'on'}
            )
            response.raise_for_status()
            print(response.content)
            cone_result = response.json()
            alerts = []
            for objectId in cone_result['hitlist']:
                alerts.append(get_lasair_object(objectId))
            return iter(alerts)

        # note: the sql SELECT must include objectId
        if 'sqlquery' in parameters and len(parameters['sqlquery'].strip()) > 0:
            response = requests.post(
                LASAIR_URL + '/objlist/',
                data={'sqlquery': parameters['sqlquery'], 'json': 'on', 'page': ''}
            )
            records = response.json()
            alerts = []
            for record in records:
                alerts.append(get_lasair_object(record['objectId']))
            return iter(alerts)

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
