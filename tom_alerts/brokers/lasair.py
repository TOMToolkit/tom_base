from tom_alerts.alerts import GenericQueryForm, GenericAlert, GenericBroker
from tom_targets.models import Target
from django import forms
import requests

LASAIR_URL = 'https://lasair.roe.ac.uk'


class LasairBrokerForm(GenericQueryForm):
    name = forms.CharField(required=True)
    cone = forms.CharField(required=False, label='Object Cone Search', help_text='Object RA and Dec')
    sqlquery = forms.CharField(required=False, label='Freeform SQL query', help_text='SQL query')


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
        if 'cone' in parameters and len(parameters['cone'].strip()) > 0:
            response = requests.post(
                LASAIR_URL + '/conesearch/',
                data={'cone': parameters['cone'], 'json': 'on'}
            )
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
            name=c['candid'],
            type='SIDEREAL',
            ra=c['ra'],
            dec=c['decl'],
            galactic_lng=alert['objectData']['glonmean'],
            galactic_lat=alert['objectData']['glatmean'],
        )
