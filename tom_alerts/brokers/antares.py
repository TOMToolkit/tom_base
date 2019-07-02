from datetime import datetime, timezone
from django import forms
from django.conf import settings
from django.core.exceptions import ImproperlyConfigured
from antares_client import Client
import requests
import logging

from tom_alerts.alerts import GenericBroker, GenericQueryForm, GenericAlert
from tom_targets.models import Target

logger = logging.getLogger(__name__)


def get_available_streams():
    response = requests.get('https://antares.noao.edu/api/streams/streams').json()
    return [(s['name'], s['name']) for s in response['result']]


class AntaresBrokerForm(GenericQueryForm):
    stream = forms.ChoiceField(choices=get_available_streams)


class AntaresBroker(GenericBroker):
    name = 'Antares'
    form = AntaresBrokerForm

    def __init__(self, *args, **kwargs):
        try:
            self.config = {
                'api_key': settings.BROKERS['antares']['api_key'],
                'api_secret': settings.BROKERS['antares']['api_secret']
            }

        except KeyError:
            raise ImproperlyConfigured('Missing antares API credentials')

    def fetch_alerts(self, parameters):
        stream = parameters['stream']
        client = Client([stream], **self.config)
        return client.iter()

    def fetch_alert(self, id):
        # Antares doesn't have programmatic access to alerts, so we use MARS here
        url = 'https://mars.lco.global/?format=json&candid={}'.format(id)
        response = requests.get(url)
        response.raise_for_status()
        return response.json()['results'][0]

    def process_reduced_data(self, target, alert=None):
        pass

    def to_target(self, alert):
        _, alert = alert
        target = Target.objects.create(
            identifier=alert['candid'],
            name=alert['objectId'],
            type='SIDEREAL',
            ra=alert['candidate']['ra'],
            dec=alert['candidate']['dec'],
            galactic_lng=alert['candidate']['l'],
            galactic_lat=alert['candidate']['b'],
        )
        return target

    def to_generic_alert(self, alert):
        _, alert = alert
        url = 'https://antares.noao.edu/alerts/data/{}'.format(alert['new_alert']['alert_id'])
        timestamp = datetime.utcfromtimestamp(alert['timestamp_unix']).replace(tzinfo=timezone.utc)
        return GenericAlert(
            timestamp=timestamp,
            url=url,
            id=alert['new_alert']['properties']['ztf_candid'],
            name=alert['new_alert']['properties']['ztf_object_id'],
            ra=alert['new_alert']['ra'],
            dec=alert['new_alert']['dec'],
            mag=alert['new_alert']['properties']['ztf_magpsf'],
            score=alert['new_alert']['properties']['ztf_rb']
        )
