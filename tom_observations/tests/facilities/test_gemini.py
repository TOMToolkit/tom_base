import unittest
from unittest import mock
from django.test import TestCase, override_settings, tag
from django.utils import timezone
from unittest.mock import patch
import requests
from requests import Response
import json
from tom_alerts.alerts import get_service_class
from tom_observations.facilities.gemini import make_request, GEMFacility
from tom_common.exceptions import ImproperCredentialsException
from tom_targets.models import Target
from tom_dataproducts.models import ReducedDatum

#tests make_request function of the Gemini facility, modeled after test_lco
class TestMakeRequest(TestCase):

    @patch('tom_observations.facilities.gemini.requests.request')
    def test_make_request(self, mock_request):
        mock_response = Response()
        mock_response._content = str.encode(json.dumps({'test': 'test'}))
        mock_response.status_code = 200
        mock_request.return_value = mock_response

        self.assertDictEqual({'test': 'test'}, make_request('GET', 'google.com', headers={'test': 'test'}).json())

        mock_response.status_code = 403
        mock_request.return_value = mock_response
        with self.assertRaises(ImproperCredentialsException):
            make_request('GET', 'google.com', headers={'test': 'test'})