from tom_alerts.alerts import GenericQueryForm, GenericAlert, GenericBroker
from tom_targets.models import Target
from django import forms
from django.conf import settings
from typing import List
import requests

LASAIR_IRIS_URL = 'https://lasair-iris.roe.ac.uk'


class LasairIrisBrokerForm(GenericQueryForm):
    queryname = forms.CharField(required=True, label='Stored Query', help_text='Stored Query Name')


class LasairIrisBroker(GenericBroker):
    """
    The ``LasairIrisBroker`` is the interface to the next generation Lasair alert broker. For information regarding the
    query format for Lasair-Iris, please see https://lasair-iris.roe.ac.uk/.
    """

    name = 'Lasair Iris'
    form = LasairIrisBrokerForm

    def __init__(self, *args, **kwargs) -> None:
        if settings.BROKERS.get('LASAIR_IRIS') and settings.BROKERS['LASAIR_IRIS'].get('api_key'):
            self.headers = {'Authorization': 'Token ' + settings.BROKERS['LASAIR_IRIS']['api_key']}
        else:
            self.headers = {}

    def fetch_alerts(self, parameters: dict) -> List[dict]:
        """
        Fetches a list of results from a Lasair stored query
        """
        query_name = parameters['queryname']
        response = requests.get(f'{LASAIR_IRIS_URL}/lasair/static/streams/{query_name}')
        response.raise_for_status()
        return iter(response.json()['digest'])

    def _query(self, selected: str, conditions: str, tables: str = 'objects') -> requests.Response:
        data = {
            'selected': selected,
            'tables': tables,
            'conditions': conditions
        }
        return requests.post(LASAIR_IRIS_URL + '/api/query/', data=data, headers=self.headers)

    def fetch_alert(self, objectId: str) -> dict:
        selected = '*'
        conditions = 'objects.objectId=' + objectId
        tables = 'objects'
        response = self._query(selected, conditions, tables)
        response.raise_for_status()
        return response.json()[0]

    def process_reduced_data(self, target, alert=None):
        pass

    def to_generic_alert(self, alert: dict) -> GenericAlert:
        score = 1 if alert['score'] == 'Within 2arcsec of PS1 star' else 0
        return GenericAlert(
            url=LASAIR_IRIS_URL + '/object/' + alert['objectId'],
            id=alert['objectId'],
            name=alert['objectId'],
            ra=alert['ramean'],
            dec=alert['decmean'],
            timestamp=alert['UTC'],
            mag=alert['rmag'],
            score=score
        )

    def to_target(self, alert):
        return Target.objects.create(
            name=alert['objectId'],
            type='SIDEREAL',
            ra=alert['ramean'],
            dec=alert['decmean'],
        )
