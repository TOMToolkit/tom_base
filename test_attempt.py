import unittest
import sys

import json
from unittest.mock import patch

from django import forms
from django.contrib.auth.models import User, Group
from django.contrib.messages import get_messages
from django.core.cache import cache
from django.test import TestCase, override_settings
from django.urls import reverse

from tom_alerts.alerts import GenericBroker, GenericQueryForm, GenericUpstreamSubmissionForm, GenericAlert
from tom_alerts.alerts import get_service_class
from tom_alerts.exceptions import AlertSubmissionException
from tom_alerts.models import BrokerQuery
from tom_observations.models import ObservationRecord
from tom_targets.models import Target

# Test alert data. Normally this would come from a remote source.
test_alerts = [
    {'id': 1, 'name': 'Tatooine', 'timestamp': '2019-07-01', 'ra': 32, 'dec': -20, 'mag': 8, 'score': 20},
    {'id': 2, 'name': 'Hoth', 'timestamp': '2019-07-02', 'ra': 66, 'dec': 50, 'mag': 3, 'score': 66},
]

#Example: can be found at https://github.com/TOMToolkit/tom_base/blob/e9dd9a3c74ddb34ce65f3d25c67e781fcd0ff588/tom_alerts/tests/tests.py
@override_settings(TOM_ALERT_CLASSES=['tom_alerts.tests.tests.TestBroker'])
class TestBrokerClass(TestCase):
    """ Test the functionality of the TestBroker, we modify the django settings to make sure
    it is the only installed broker.
    """
    def test_get_broker_class(self):
        self.assertEqual(TestBroker, get_service_class('TEST')) #Check that the result = the service class 'TEST'

    def test_get_invalid_broker(self):
        with self.assertRaises(ImportError): #Raises an import error if:
            get_service_class('MARS') #The invalid broker is returned


#My attempt at a test
modulename = 'one'
nestedmodulename = 'two'
#sys.modules['one']={}
class TestModuleImport(unittest.TestCase):

#Failure to import module
    def test_import_invalid_mod(self):
        with self.assertRaises(ImportError): #Raises an import error if:
            modulename not in sys.modules #The import_module command fails

#Failure to import nested module from a package
    def test_import_invalid_pkg(self):
        with self.assertRaises(ImportError):
            nestedmodulename not in sys.modules #stored as nestedmodulename=sys.modules['packagename.nestedmodulename']
