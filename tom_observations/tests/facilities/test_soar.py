import json
from requests import Response
from unittest.mock import patch

from django.test import TestCase

from tom_common.exceptions import ImproperCredentialsException
from tom_observations.facilities.soar import make_request, SOARImagingObservationForm
from tom_observations.facilities.soar import SOARSpectroscopyObservationForm
from tom_observations.tests.factories import SiderealTargetFactory


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
        'default_configuration_type': 'SPECTRUM'
    },
    '0M4-SCICAM-SBIG': {
        'type': 'IMAGE', 'class': '0m4', 'name': '0.4 meter SBIG', 'optical_elements': {
            'filters': [
                {'name': 'Opaque', 'code': 'opaque', 'schedulable': False, 'default': False},
                {'name': '100um Pinhole', 'code': '100um-Pinhole', 'schedulable': False, 'default': False},
            ]
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
        'modes': {
            'rotator': {
                'type': 'rotator',
                'modes': [
                    {'name': 'Sky Position', 'code': 'SKY'}
                ]
            },
            'readout': {
                'type': 'readout',
                'modes': [
                    {'name': 'GHTS Red Camera 400m1 2x2', 'code': 'GHTS Red Camera 400m1 2x2'},
                ]
            }
        },
        'default_configuration_type': 'SPECTRUM'
    },
    'SOAR_GHTS_REDCAM_IMAGER': {
        'type': 'IMAGE', 'class': '4m0', 'name': 'Goodman Spectrograph RedCam Imager', 'optical_elements': {
            'filters': [
                {'name': 'Clear', 'code': 'air', 'schedulable': True, 'default': False},
                {'name': 'GHTS u-SDSS', 'code': 'u-SDSS', 'schedulable': False, 'default': False},
                {'name': 'GHTS g-SDSS', 'code': 'g-SDSS', 'schedulable': True, 'default': False},
                {'name': 'GHTS r-SDSS', 'code': 'r-SDSS', 'schedulable': True, 'default': True},
                {'name': 'GHTS i-SDSS', 'code': 'i-SDSS', 'schedulable': True, 'default': False},
                {'name': 'GHTS z-SDSS', 'code': 'z-SDSS', 'schedulable': False, 'default': False},
                {'name': 'GHTS VR', 'code': 'VR', 'schedulable': True, 'default': False}
            ]
        },
        'default_configuration_type': 'EXPOSE'
    }
}


class TestMakeRequest(TestCase):

    @patch('tom_observations.facilities.soar.requests.request')
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


@patch('tom_observations.facilities.ocs.OCSBaseForm.proposal_choices')
@patch('tom_observations.facilities.ocs.OCSBaseForm._get_instruments')
class TestSOARImagingObservationForm(TestCase):
    def setUp(self):
        self.st = SiderealTargetFactory.create()
        self.valid_form_data = {
            'name': 'test', 'facility': 'SOAR', 'target_id': self.st.id, 'ipp_value': 0.5, 'start': '2020-11-03',
            'end': '2020-11-04', 'c_1_ic_1_exposure_count': 1, 'c_1_ic_1_exposure_time': 30.0, 'c_1_max_airmass': 3,
            'c_1_min_lunar_distance': 20, 'observation_mode': 'NORMAL', 'proposal': 'sampleproposal',
            'c_1_ic_1_filter': 'air', 'c_1_instrument_type': 'SOAR_GHTS_REDCAM_IMAGER'
        }

    def test_instrument_choices(self, mock_get_instruments, mock_proposals):
        """Test SOARImagingObservationForm._instrument_choices."""
        mock_proposals.return_value = [('sampleproposal', 'Sample Proposal')]
        mock_get_instruments.return_value = {k: v for k, v in instrument_response.items() if 'SOAR' in k}
        form = SOARImagingObservationForm(self.valid_form_data)

        inst_choices = form.instrument_choices()
        self.assertIn(('SOAR_GHTS_REDCAM_IMAGER', 'Goodman Spectrograph RedCam Imager'), inst_choices)
        self.assertNotIn(('SOAR_GHTS_REDCAM', 'Goodman Spectrograph RedCam'), inst_choices)
        self.assertEqual(len(inst_choices), 1)

    def test_filter_choices(self, mock_get_instruments, mock_proposals):
        """Test SOARImagingObservationForm._filter_choices."""
        mock_proposals.return_value = [('sampleproposal', 'Sample Proposal')]
        mock_get_instruments.return_value = {k: v for k, v in instrument_response.items() if 'SOAR' in k}
        form = SOARImagingObservationForm(self.valid_form_data)

        filter_choices = form.filter_choices_for_group('filters')
        for expected in [('air', 'Clear'), ('g-SDSS', 'GHTS g-SDSS'),
                         ('r-SDSS', 'GHTS r-SDSS'), ('i-SDSS', 'GHTS i-SDSS'),
                         ('VR', 'GHTS VR')]:
            self.assertIn(expected, filter_choices)
        for not_expected in [('slit_1.0as', '1.0 arcsec slit')]:
            self.assertNotIn(not_expected, filter_choices)
        self.assertEqual(len(filter_choices), 5)


class TestSOARSpectroscopyObservationForm(TestCase):
    def setUp(self):
        self.st = SiderealTargetFactory.create()
        self.valid_form_data = {
            'name': 'test', 'facility': 'SOAR', 'target_id': self.st.id, 'ipp_value': 0.5, 'start': '2020-11-03',
            'end': '2020-11-04', 'c_1_ic_1_exposure_count': 1, 'c_1_ic_1_exposure_time': 30.0, 'c_1_max_airmass': 3,
            'c_1_min_lunar_distance': 20, 'observation_mode': 'NORMAL', 'proposal': 'sampleproposal',
            'c_1_ic_1_rotator_mode': 'SKY', 'c_1_ic_1_slit': 'slit_1.0as', 'c_1_ic_1_grating': 'SYZY_400',
            'c_1_instrument_type': 'SOAR_GHTS_REDCAM', 'c_1_ic_1_rotator_angle': 1.0,
            'c_1_ic_1_readout_mode': 'GHTS Red Camera 400m1 2x2'
        }

    @patch('tom_observations.facilities.ocs.OCSBaseForm.proposal_choices')
    @patch('tom_observations.facilities.ocs.OCSBaseForm._get_instruments')
    def test_instrument_choices(self, mock_get_instruments, mock_proposals):
        """Test SOARSpectroscopyObservationForm._instrument_choices."""
        mock_proposals.return_value = [('sampleproposal', 'Sample Proposal')]
        mock_get_instruments.return_value = {k: v for k, v in instrument_response.items() if 'SOAR' in k}
        form = SOARSpectroscopyObservationForm(self.valid_form_data)

        inst_choices = form.instrument_choices()
        self.assertIn(('SOAR_GHTS_REDCAM', 'Goodman Spectrograph RedCam'), inst_choices)
        self.assertNotIn(('SOAR_GHTS_REDCAM_IMAGER', 'Goodman Spectrograph RedCam Imager'), inst_choices)
        self.assertEqual(len(inst_choices), 1)

    @patch('tom_observations.facilities.ocs.OCSBaseForm.proposal_choices')
    @patch('tom_observations.facilities.ocs.OCSBaseForm._get_instruments')
    def test_slit_choices(self, mock_get_instruments, mock_proposals):
        """Test SOARSpectroscopyObservationForm slit choices"""
        mock_proposals.return_value = [('sampleproposal', 'Sample Proposal')]
        mock_get_instruments.return_value = {k: v for k, v in instrument_response.items() if 'SOAR' in k}
        form = SOARSpectroscopyObservationForm(self.valid_form_data)

        slit_choices = form.filter_choices_for_group('slits')
        for expected in [('slit_1.0as', '1.0 arcsec slit')]:
            self.assertIn(expected, slit_choices)
        for not_expected in [('u-SDSS', 'GHTS u-SDSS'), ('i-SDSS', 'GHTS i-SDSS')]:
            self.assertNotIn(not_expected, slit_choices)
        self.assertEqual(len(slit_choices), 1)

    @patch('tom_observations.facilities.ocs.OCSBaseForm.proposal_choices')
    @patch('tom_observations.facilities.ocs.OCSBaseForm._get_instruments')
    @patch('tom_observations.facilities.soar.SOARSpectroscopyObservationForm.validate_at_facility')
    def test_build_instrument_config(self, mock_validate, mock_insts, mock_proposals):
        mock_validate.return_value = {}
        mock_insts.return_value = {k: v for k, v in instrument_response.items() if 'SOAR' in k}
        mock_proposals.return_value = [('sampleproposal', 'Sample Proposal')]

        # Test that optical_elements['slit'] and optical_elements['grating] are populated when filter is included
        with self.subTest():
            form = SOARSpectroscopyObservationForm(self.valid_form_data)
            self.assertTrue(form.is_valid())
            self.assertEqual(
                {
                    'exposure_count': self.valid_form_data['c_1_ic_1_exposure_count'],
                    'exposure_time': self.valid_form_data['c_1_ic_1_exposure_time'],
                    'optical_elements': {'slit': self.valid_form_data['c_1_ic_1_slit'],
                                         'grating': self.valid_form_data['c_1_ic_1_grating']},
                    'rotator_mode': self.valid_form_data['c_1_ic_1_rotator_mode'],
                    'extra_params': {'rotator_angle': self.valid_form_data['c_1_ic_1_rotator_angle']},
                    'mode': self.valid_form_data['c_1_ic_1_readout_mode'],
                },
                form._build_instrument_config(self.valid_form_data['c_1_instrument_type'], 1, 1)
            )
