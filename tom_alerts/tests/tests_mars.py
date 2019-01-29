import json
from requests import Response

from django.test import TestCase, override_settings
from unittest import mock
from django.contrib.auth.models import User
from django.urls import reverse

from tom_alerts.brokers.mars import MARSBroker
from tom_alerts.alerts import get_service_class
from tom_alerts.models import BrokerQuery
from tom_targets.models import Target
from tom_reduced_data.models import ReducedDatum, ReducedDatumSource


@override_settings(TOM_ALERT_CLASSES=['tom_alerts.brokers.mars.MARSBroker'])
class TestMARSBrokerClass(TestCase):
    """ Test the functionality of the MARSBroker, we modify the django settings to make sure
    it is the only installed broker.
    """
    def setUp(self):
        self.test_target = Target.objects.create(identifier='ZTF18aberpsh')
        self.test_source = ReducedDatumSource.objects.create(name='MARS', location=11053318)
        with open('tom_alerts/tests/data/mars_response_data.json') as f:
            self.test_data = json.load(f)
        ReducedDatum.objects.create(
            source=self.test_source,
            target=self.test_target,
            data_type='PHOTOMETRY',
            timestamp=3,
            value=12
        )

    def test_get_broker_class(self):
        self.assertEqual(MARSBroker, get_service_class('MARS'))

    def test_get_invalid_broker(self):
        with self.assertRaises(ImportError):
            get_service_class('LASAIR')

    @mock.patch('tom_alerts.brokers.mars.requests.get')
    def test_fetch_alerts(self, mock_requests_get):
        mock_return_data = {
            "has_next": "false",
            "has_prev": "false",
            "pages": 1,
            "results": [self.test_data['results'][1]]
        }
        mock_response = Response()
        mock_response._content = str.encode(json.dumps(mock_return_data))
        mock_response.status_code = 200
        mock_requests_get.return_value = mock_response

        alerts = MARSBroker().fetch_alerts({'objectId': 'ZTF18aberpsh'})
        self.assertEqual(self.test_data['results'][1]['objectId'], alerts[0]['objectId'])

    def test_process_reduced_data_with_alert(self):
        test_alert = self.test_data['results'][1]
        test_alert['prv_candidate'] = [
            {
                'candidate': {
                    'jd': 4,
                    'magpsf': 13
                }
            }
        ]

        MARSBroker().process_reduced_data(self.test_target, alert=test_alert)
        reduced_data = ReducedDatum.objects.filter(target=self.test_target, source=self.test_source)
        reduced_data_sources = ReducedDatumSource.objects.filter(name='MARS')
        self.assertEqual(reduced_data.count(), 2)
        self.assertEqual(reduced_data_sources.count(), 1)

    @mock.patch('tom_alerts.brokers.mars.MARSBroker.fetch_alert')
    def test_process_reduced_data_no_alert(self, mock_fetch_alert):
        self.test_data = self.test_data['results'][1]
        self.test_data['prv_candidate'] = [
            {
                'candidate': {
                    'jd': 4,
                    'magpsf': 13
                }
            }
        ]
        mock_fetch_alert.return_value = self.test_data

        MARSBroker().process_reduced_data(self.test_target)
        reduced_data = ReducedDatum.objects.filter(target=self.test_target)
        reduced_data_sources = ReducedDatumSource.objects.filter(name='MARS')
        self.assertEqual(reduced_data.count(), 2)
        self.assertEqual(reduced_data_sources.count(), 1)

    def test_to_target(self):
        test_alert = self.test_data['results'][1]

        created_target = MARSBroker().to_target(test_alert)
        self.assertEqual(created_target.name, 'ZTF18aberpsh')

    def test_to_generic_alert(self):
        test_alert = self.test_data['results'][1]

        created_alert = MARSBroker().to_generic_alert(test_alert)
        self.assertEqual(created_alert.name, 'ZTF18aberpsh')
