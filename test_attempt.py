import unittest
import sys

import json
from unittest.mock import patch
from unittest.mock import MagicMock

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

class TestModuleImport(TestCase):

#Failure to import module
    def test_import_invalid_mod(self):
        with self.subTest('Test that an invalid import returns an import error.'):
            with patch('tom_observations.api_views.get_service_class') as mock_get_service_class:
                mock_get_service_class.side_effect = ImportError('Import failed. Did you provide the correct path?')
                result = mock_get_service_class()
                self.assertIn('Import failed. Did you provide the correct path?', result)
