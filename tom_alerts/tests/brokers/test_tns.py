from django.test import TestCase
from tom_targets.tests.factories import SiderealTargetFactory

from tom_alerts.brokers import tns


class TestClassSN(TestCase):
    """
    Class describing unittests for the target planet priority functions
    """
    def setUp(self):
        st1 = SiderealTargetFactory.create()
        st1.name = 'Gaia23dje'
        st1.ra = 41.41608
        st1.dec = -20.80996
        self.params = {
            'target': st1,
            'objname': '2023xrs'
        }

    def test_tns_response(self):
        parameters = {
            'ra': self.params['target'].ra,
            'dec': self.params['target'].dec,
            'radius': 1.0,
            'units': 'arcsec',
            'objname': self.params['objname'],
        }

        tns_classes = tns.TNSBroker.fetch_tns_class(parameters)
        self.assertEqual(tns_classes, 'SN Ic-BL')
