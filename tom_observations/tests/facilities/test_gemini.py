import json
from unittest.mock import patch
from requests import Response

from django.test import TestCase

from tom_common.exceptions import ImproperCredentialsException
from tom_observations.facilities.gemini import make_request


class TestMakeRequest(TestCase):

    '''
    Tests make_request function of the Gemini facility, modeled after test_lco
    '''

    @patch('tom_observations.facilities.gemini.requests.request')
    def test_make_request(self, mock_request):
        '''
        Response object contains server's response to HTTP request
        '''
        mock_response = Response()
        mock_response._content = str.encode(json.dumps({'test': 'test'}))
        mock_response.status_code = 200
        mock_request.return_value = mock_response

        self.assertDictEqual({'test': 'test'}, make_request('GET', 'google.com', headers={'test': 'test'}).json())

        mock_response.status_code = 403
        mock_request.return_value = mock_response
        with self.assertRaises(ImproperCredentialsException):
            make_request('GET', 'google.com', headers={'test': 'test'})
