from datetime import datetime, timezone
from django import forms
from django.conf import settings
from django.core.exceptions import ImproperlyConfigured
from antares_client import Client
import requests

from tom_alerts.alerts import GenericBroker, GenericQueryForm, GenericAlert
from tom_targets.models import Target


class AntaresBrokerForm(GenericQueryForm):
    alert_limit = forms.IntegerField(min_value=1)
    stream = forms.CharField()


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
        alert_limit = parameters['alert_limit']
        with Client([stream], **self.config) as client:
            alerts = []
            for topic, alert in client.iter(num_alerts=alert_limit):
                alerts.append(alert)

            return alerts

    def fetch_alert(self, id):
        # Antares doesn't have programmatic access to alerts, so we use MARS here
        url = 'https://mars.lco.global/?format=json&candid={}'.format(id)
        response = requests.get(url)
        response.raise_for_status()
        return response.json()['results'][0]

    def process_reduced_data(self, target, alert=None):
        pass

    def to_target(self, alert):
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
