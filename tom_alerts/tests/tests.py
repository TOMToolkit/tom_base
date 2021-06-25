import unittest
from unittest import mock
from django.test import TestCase, override_settings, tag
from django.utils import timezone
from unittest.mock import patch
import requests
from requests import Response
import json
from tom_alerts.alerts import get_service_class
from tom_alerts.brokers.lasair import LasairBroker, LasairBrokerForm
from tom_alerts.brokers.gaia import GaiaBroker
from tom_common.exceptions import ImproperCredentialsException
from tom_targets.models import Target
from tom_dataproducts.models import ReducedDatum

'''
alert1 = {
    
    'candidates': {
       'candid': 617122521615015023,
       'b': 0.70548695469711,
       'dec': -10.5296018,
       'jd': 2458371.6225231,
       'l': 20.7124513780029,
       'magpsf': 16.321626663208,
       'ra': 276.5843017,
       'rb': 0.990000009536743,
       'wall_time': 'Mon, 10 Sep 2018 02:56:25 GMT',
    },
    'lco_id': 11296149,
    'objectId': 'ZTF18abbkloa',
}
@override_settings(TOM_ALERT_CLASSES=['tom_alerts.brokers.lasair.LasairBroker'])
class TestLasairBrokerClass(TestCase):
    """ Test the functionality of the LasairBroker, we modify the django settings to make sure
    it is the only installed broker.
    """
    def setUp(self):
        self.test_target = Target.objects.create(name='ZTF18aberpsh')
        ReducedDatum.objects.create(
            source_name='MARS',
            source_location=11053318,
            target=self.test_target,
            data_type='photometry',
            timestamp=timezone.now(),
            value=12
        )
        alert2 = alert1.copy()
        alert2['lco_id'] = 11053318
        alert2['objectId'] = 'ZTF18aberpsh'
        self.test_data = [alert1, alert2] 
    @mock.patch('tom_alerts.brokers.lasair.LasairBroker.fetch_alert')
    def test_to_target(self, alert):
        testalert = self.test_data[0]
        created_target = LasairBroker().to_target(testalert)
        self.assertEqual(created_target.name, 'ZTF18abbkloa')
'''

alert1 = {
    'candid': 617122521615015023,
    'candidate': {
       'b': 0.70548695469711,
       'dec': -10.5296018,
       'jd': 2458371.6225231,
       'l': 20.7124513780029,
       'magpsf': 16.321626663208,
       'ra': 276.5843017,
       'rb': 0.990000009536743,
       'wall_time': 'Mon, 10 Sep 2018 02:56:25 GMT',
    },
    'lco_id': 11296149,
    'objectId': 'ZTF18abbkloa',
}
#tests get_broker_class for Gaia broker, modeled after Mars broker
@override_settings(TOM_ALERT_CLASSES=['tom_alerts.brokers.gaia.GaiaBroker'])
class TestGaiaBrokerClass(TestCase):
    """ Test the functionality of the GaiaBroker, we modify the django settings to make sure
    it is the only installed broker.
    """
    def setUp(self):
        self.test_target = Target.objects.create(name='ZTF18aberpsh')
        ReducedDatum.objects.create(
            source_name='Gaia',
            source_location=11053318,
            target=self.test_target,
            data_type='photometry',
            timestamp=timezone.now(),
            value=12
        )
        alert2 = alert1.copy()
        alert2['lco_id'] = 11053318
        alert2['objectId'] = 'ZTF18aberpsh'
        self.test_data = [alert1, alert2]

    def test_get_broker_class(self):
        self.assertEqual(GaiaBroker, get_service_class('Gaia'))