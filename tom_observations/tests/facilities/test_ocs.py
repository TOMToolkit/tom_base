from requests import Response
from unittest.mock import patch
import json

from django.test import TestCase
from tom_observations.facilities.ocs import (make_request, OCSBaseForm, OCSFacility, OCSTemplateBaseForm)
from tom_common.exceptions import ImproperCredentialsException


instrument_response = {
    '2M0-FLOYDS-SCICAM': {
        'type': 'SPECTRA', 'class': '2m0', 'name': '2.0 meter FLOYDS', 'optical_elements': {
            'slits': [
                {'name': '6.0 arcsec slit', 'code': 'slit_6.0as', 'schedulable': True, 'default': False},
                {'name': '1.6 arcsec slit', 'code': 'slit_1.6as', 'schedulable': True, 'default': False},
                {'name': '2.0 arcsec slit', 'code': 'slit_2.0as', 'schedulable': True, 'default': False},
                {'name': '1.2 arcsec slit', 'code': 'slit_1.2as', 'schedulable': True, 'default': False}
            ]
        },
        'modes': {
            'rotator': {
                'type': 'rotator',
                'modes': [
                    {'name': 'Sky Position', 'code': 'SKY'}
                ]
            }
        },
        'default_configuration_type': 'SPECTRUM'
    },
    '1M0-NRES-SCICAM': {
        'type': 'SPECTRA', 'class': '1m0', 'name': '1.0 meter NRES',
        'optical_elements': {},
        'default_configuration_type': 'NRES_SPECTRUM'
    },
    '0M4-SCICAM-SBIG': {
        'type': 'IMAGE', 'class': '0m4', 'name': '0.4 meter SBIG', 'optical_elements': {
            'filters': [
                {"name": "Bessell-U", "code": "U", "schedulable": True, "default": False},
                {"name": "Bessell-B", "code": "B", "schedulable": True, "default": False},
                {"name": "Bessell-V", "code": "V", "schedulable": True, "default": False},
                {"name": "Bessell-R", "code": "R", "schedulable": True, "default": False},
                {"name": "Bessell-I", "code": "I", "schedulable": True, "default": False},
                {"name": "SDSS-up", "code": "up", "schedulable": True, "default": False},
                {"name": "SDSS-gp", "code": "gp", "schedulable": True, "default": False},
                {"name": "SDSS-rp", "code": "rp", "schedulable": True, "default": False},
                {"name": "SDSS-ip", "code": "ip", "schedulable": True, "default": False},
                {"name": "PanSTARRS-Z", "code": "zs", "schedulable": True, "default": False},
                {"name": "PanSTARRS-w", "code": "w", "schedulable": True, "default": False},
                {'name': 'Opaque', 'code': 'opaque', 'schedulable': False, 'default': False},
                {'name': '100um Pinhole', 'code': '100um-Pinhole', 'schedulable': False, 'default': False},
            ]
        },
        'modes': {
            'guiding': {
                'type': 'guiding',
                'modes': [
                    {'name': 'On', 'overhead': 0.0, 'code': 'ON'},
                    {'name': 'Off', 'overhead': 0.0, 'code': 'OFF'},
                ],
                'default': 'ON'
            }
        },
        'default_configuration_type': 'EXPOSE'
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
        'default_configuration_type': 'SPECTRUM'
    },
    '2M0-SCICAM-MUSCAT': {
        'type': 'IMAGE', 'class': '2m0', 'name': '2.0 meter Muscat',
        'optical_elements': {
            'diffuser_g_positions': [
                {'name': 'In Beam', 'code': 'in', 'schedulable': True, 'default': True},
                {'name': 'Out of Beam', 'code': 'out', 'schedulable': True, 'default': True}
            ],
            'diffuser_r_positions': [
                {'name': 'In Beam', 'code': 'in', 'schedulable': True, 'default': False},
                {'name': 'Out of Beam', 'code': 'out', 'schedulable': True, 'default': True}
            ],
            'diffuser_i_positions': [
                {'name': 'In Beam', 'code': 'in', 'schedulable': True, 'default': False},
                {'name': 'Out of Beam', 'code': 'out', 'schedulable': True, 'default': True}
            ],
            'diffuser_z_positions': [
                {'name': 'In Beam', 'code': 'in', 'schedulable': True, 'default': False},
                {'name': 'Out of Beam', 'code': 'out', 'schedulable': True, 'default': True}
            ]
        },
        'modes': {
            'guiding': {
                'type': 'guiding',
                'modes': [
                    {'name': 'On', 'overhead': 0.0, 'code': 'ON'},
                    {'name': 'Muscat G Guiding', 'overhead': 0.0, 'code': 'MUSCAT_G'},
                ],
                'default': 'ON'
            },
            'exposure': {
                'type': 'exposure',
                'modes': [
                    {'name': 'Muscat Synchronous Exposure Mode', 'overhead': 0.0, 'code': 'SYNCHRONOUS'},
                    {'name': 'Muscat Asynchronous Exposure Mode', 'overhead': 0.0, 'code': 'ASYNCHRONOUS'}
                ],
                'default': 'SYNCHRONOUS'
            }
        },
        'default_configuration_type': 'EXPOSE'
    }
}


def generate_ocs_instrument_choices():
    return {k: v for k, v in instrument_response.items()}


def generate_ocs_proposal_choices():
    return [('sampleproposal', 'Sample Proposal')]


class TestMakeRequest(TestCase):

    @patch('tom_observations.facilities.ocs.requests.request')
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


class TestOCSBaseForm(TestCase):
    @patch('tom_observations.facilities.ocs.OCSBaseForm.proposal_choices')
    @patch('tom_observations.facilities.ocs.make_request')
    @patch('tom_observations.facilities.ocs.cache')
    def test_get_instruments(self, mock_cache, mock_make_request, mock_proposals):
        mock_response = Response()
        mock_response._content = str.encode(json.dumps(generate_ocs_instrument_choices()))
        mock_response.status_code = 200
        mock_make_request.return_value = mock_response

        # Test that cached value is returned
        with self.subTest():
            test_instruments = {'test instrument': {'type': 'IMAGE', 'name': 'Test Instrument'}}
            mock_cache.get.return_value = test_instruments
            form = OCSTemplateBaseForm()

            instruments = form._get_instruments()
            self.assertDictContainsSubset(test_instruments, instruments)
            self.assertNotIn('0M4-SCICAM-SBIG', instruments)

        # Test that empty cache results in mock_instruments, and cache.set is called
        with self.subTest():
            mock_cache.get.return_value = None
            form = OCSTemplateBaseForm()

            instruments = form._get_instruments()
            self.assertIn('0M4-SCICAM-SBIG', instruments)
            self.assertIn('SOAR_GHTS_REDCAM', instruments)
            self.assertDictContainsSubset({'type': 'IMAGE'}, instruments['0M4-SCICAM-SBIG'])
            mock_cache.set.assert_called()

    @patch('tom_observations.facilities.ocs.OCSBaseForm._get_instruments')
    def test_instrument_to_type(self, mock_get_instruments):
        mock_get_instruments.return_value = generate_ocs_instrument_choices()
        # Test instrument_to_type method.
        form = OCSBaseForm()
        self.assertEqual('SPECTRUM', form.instrument_to_default_configuration_type('2M0-FLOYDS-SCICAM'))
        self.assertEqual('NRES_SPECTRUM', form.instrument_to_default_configuration_type('1M0-NRES-SCICAM'))
        self.assertEqual('EXPOSE', form.instrument_to_default_configuration_type('0M4-SCICAM-SBIG'))

    @patch('tom_observations.facilities.ocs.OCSBaseForm._get_instruments')
    def test_instrument_choices(self, mock_get_instruments):
        mock_get_instruments.return_value = generate_ocs_instrument_choices()
        form = OCSBaseForm()

        inst_choices = form.instrument_choices()
        self.assertIn(('2M0-FLOYDS-SCICAM', '2.0 meter FLOYDS'), inst_choices)
        self.assertIn(('0M4-SCICAM-SBIG', '0.4 meter SBIG'), inst_choices)
        self.assertIn(('2M0-SCICAM-MUSCAT', '2.0 meter Muscat'), inst_choices)
        self.assertEqual(len(inst_choices), 5)

    @patch('tom_observations.facilities.ocs.OCSBaseForm._get_instruments')
    def test_filter_choices(self, mock_get_instruments, ):
        mock_get_instruments.return_value = generate_ocs_instrument_choices()
        form = OCSBaseForm()

        filter_choices = form.all_optical_element_choices()
        for expected in [('rp', 'SDSS-rp'), ('R', 'Bessell-R'), ('slit_6.0as', '6.0 arcsec slit')]:
            self.assertIn(expected, filter_choices)
        self.assertEqual(len(filter_choices), 19)

    @patch('tom_observations.facilities.ocs.OCSBaseForm._get_instruments')
    @patch('tom_observations.facilities.ocs.make_request')
    def test_proposal_choices(self, mock_make_request, mock_get_instruments):
        mock_get_instruments.return_value = generate_ocs_instrument_choices()
        mock_response = Response()
        mock_response._content = str.encode(json.dumps({'proposals': [
            {'id': 'ActiveProposal', 'title': 'Active', 'current': True},
            {'id': 'InactiveProposal', 'title': 'Inactive', 'current': False}]
        }))
        mock_response.status_code = 200
        mock_make_request.return_value = mock_response
        form = OCSTemplateBaseForm()

        proposal_choices = form.proposal_choices()
        self.assertIn(('ActiveProposal', 'Active (ActiveProposal)'), proposal_choices)
        self.assertNotIn(('InactiveProposal', 'Inactive (InactiveProposal)'), proposal_choices)


class TestOCSFacility(TestCase):
    def setUp(self):
        self.lco = OCSFacility()

    @patch('tom_observations.facilities.ocs.make_request')
    def test_get_facility_status_fails_gracefully(self, mock_make_request):
        mock_response = Response()
        mock_response._content = str.encode('ConnectionError - Error retrieving telescope states')
        mock_response.status_code = 502
        mock_make_request.return_value = mock_response
        facility_status = self.lco.get_facility_status()
        self.assertEqual(facility_status.get('sites'), [])

    @patch('tom_observations.facilities.ocs.make_request')
    def test_get_requestgroup_id(self, mock_make_request):
        mock_response = Response()
        mock_response._content = str.encode(json.dumps({
            'count': 1,
            'results': [{
                'id': 1073496
            }]
        }))
        mock_response.status_code = 200
        mock_make_request.return_value = mock_response

        with self.subTest('Test that a correct response results in a valid id.'):
            requestgroup_id = self.lco._get_requestgroup_id(1234567)
            self.assertEqual(requestgroup_id, 1073496)

        with self.subTest('Test that an empty response results in no id.'):
            mock_response._content = str.encode(json.dumps({
                'count': 0,
                'results': []
            }))
            requestgroup_id = self.lco._get_requestgroup_id(1234567)
            self.assertIsNone(requestgroup_id)

        with self.subTest('Test that multiple results returns no id.'):
            mock_response._content = str.encode(json.dumps({
                'count': 2,
                'results': [{'id': 1073496}, {'id': 1073497}]
            }))
            requestgroup_id = self.lco._get_requestgroup_id(1234567)
            self.assertIsNone(requestgroup_id)
