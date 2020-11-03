import json
from requests import Response
from unittest.mock import patch

from django.test import TestCase

from tom_observations.facilities.lco import make_request
from tom_observations.facilities.lco import LCOBaseForm, LCOBaseObservationForm


instrument_response = {
    '2M0-FLOYDS-SCICAM': {
        'type': 'SPECTRA', 'class': '2m0', 'name': '2.0 meter FLOYDS', 'optical_elements': {
            'slits': [
              {'name': '6.0 arcsec slit', 'code': 'slit_6.0as', 'schedulable': True, 'default': False},
              {'name': '1.6 arcsec slit', 'code': 'slit_1.6as', 'schedulable': True, 'default': False},
              {'name': '2.0 arcsec slit', 'code': 'slit_2.0as', 'schedulable': True, 'default': False},
              {'name': '1.2 arcsec slit', 'code': 'slit_1.2as', 'schedulable': True, 'default': False}
            ]
        }
    },
    '0M4-SCICAM-SBIG': {
        'type': 'IMAGE', 'class': '0m4', 'name': '0.4 meter SBIG', 'optical_elements': {
            'filters': [
                {'name': 'Opaque', 'code': 'opaque', 'schedulable': False, 'default': False},
                {'name': '100um Pinhole', 'code': '100um-Pinhole', 'schedulable': False, 'default': False},
            ]
        },
    },
    'SOAR_GHTS_REDCAM': {
        'type': 'SPECTRA', 'class': '4m0', 'name': 'Goodman Spectrograph RedCam', 'optical_elements': {
            'gratings': [
                {'name': '400 line grating', 'code': 'SYZY_400', 'schedulable': True, 'default': True},
            ],
            'slits': [
                {'name': '1.0 arcsec slit', 'code': 'slit_1.0as', 'schedulable': True, 'default': True}
            ]
        },
    }
}


class TestMakeRequest(TestCase):

    @patch('tom_observations.facilities.lco.requests.request')
    def test_make_request(self, mock_request):
        mock_response = Response()
        mock_response._content = str.encode(json.dumps({'test': 'test'}))
        mock_response.status_code = 200
        mock_request.return_value = mock_response

        self.assertDictEqual({'test': 'test'}, make_request('GET', 'google.com', headers={'test': 'test'}).json())


class TestLCOBaseForm(TestCase):

    @patch('tom_observations.facilities.lco.make_request')
    @patch('tom_observations.facilities.lco.cache')
    def test_get_instruments(self, mock_cache, mock_make_request):
        mock_response = Response()
        mock_response._content = str.encode(json.dumps(instrument_response))
        mock_response.status_code = 200
        mock_make_request.return_value = mock_response

        # Test that cached value is returned
        with self.subTest():
            test_instruments = {'test instrument': {'type': 'IMAGE'}}
            mock_cache.get.return_value = test_instruments

            instruments = LCOBaseForm._get_instruments()
            self.assertDictContainsSubset({'test instrument': {'type': 'IMAGE'}}, instruments)
            self.assertNotIn('0M4-SCICAM-SBIG', instruments)

        # Test that empty cache results in mock_instruments, and cache.set is called
        with self.subTest():
            mock_cache.get.return_value = None

            instruments = LCOBaseForm._get_instruments()
            self.assertIn('0M4-SCICAM-SBIG', instruments)
            self.assertDictContainsSubset({'type': 'IMAGE'}, instruments['0M4-SCICAM-SBIG'])
            self.assertNotIn('SOAR_GHTS_REDCAM', instruments)
            mock_cache.set.assert_called()

    @patch('tom_observations.facilities.lco.LCOBaseForm._get_instruments')
    def test_instrument_choices(self, mock_get_instruments):
        mock_get_instruments.return_value = {k: v for k, v in instrument_response.items() if 'SOAR' not in k}

        inst_choices = LCOBaseForm.instrument_choices()
        self.assertIn(('2M0-FLOYDS-SCICAM', '2.0 meter FLOYDS'), inst_choices)
        self.assertIn(('0M4-SCICAM-SBIG', '0.4 meter SBIG'), inst_choices)

    @patch('tom_observations.facilities.lco.LCOBaseForm._get_instruments')
    def test_filter_choices(self, mock_get_instruments):
        mock_get_instruments.return_value = {k: v for k, v in instrument_response.items() if 'SOAR' not in k}

        filter_choices = LCOBaseForm.filter_choices()
        for expected in [('opaque', 'Opaque'), ('100um-Pinhole', '100um Pinhole'), ('slit_6.0as', '6.0 arcsec slit')]:
            self.assertIn(expected, filter_choices)
        self.assertEqual(len(filter_choices), 6)

    @patch('tom_observations.facilities.lco.make_request')
    def test_proposal_choices(self, mock_make_request):
        mock_response = Response()
        mock_response._content = str.encode(json.dumps({'proposals':
            [{'id': 'ActiveProposal', 'title': 'Active', 'current': True},
             {'id': 'InactiveProposal', 'title': 'Inactive', 'current': False}]
        }))
        mock_response.status_code = 200
        mock_make_request.return_value = mock_response

        proposal_choices = LCOBaseForm.proposal_choices()
        self.assertIn(('ActiveProposal', 'Active (ActiveProposal)'), proposal_choices)
        self.assertNotIn(('InactiveProposal', 'Inactive (InactiveProposal)'), proposal_choices)


class TestLCOBaseObservationForm(TestCase):
    pass


class TestLCOImagingObservationForm(TestCase):
    pass


class TestLCOSpectroscopyObservationForm(TestCase):
    pass


class TestLCOPhotometricSequenceForm(TestCase):
    pass


class TestLCOSpectroscopicSequenceForm(TestCase):
    pass


class TestLCOObservationTemplateForm(TestCase):
    pass


class TestLCOFacility(TestCase):
    pass
