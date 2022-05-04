import json
from requests import Response
from unittest.mock import patch

from django.test import TestCase

from tom_common.exceptions import ImproperCredentialsException
from tom_observations.facilities.soar import make_request, SOARBaseObservationForm, SOARImagingObservationForm
from tom_observations.facilities.soar import SOARSpectroscopyObservationForm
from tom_observations.tests.factories import NonSiderealTargetFactory, SiderealTargetFactory


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


class TestSOARBaseObservationForm(TestCase):

    def setUp(self):
        self.st = SiderealTargetFactory.create()
        self.nst = NonSiderealTargetFactory.create(scheme='MPC_MINOR_PLANET')
        self.valid_form_data = {
            'name': 'test', 'facility': 'SOAR', 'target_id': self.st.id, 'ipp_value': 0.5, 'start': '2020-11-03',
            'end': '2020-11-04', 'exposure_count': 1, 'exposure_time': 30, 'max_airmass': 3,
            'min_lunar_distance': 20, 'observation_mode': 'NORMAL',
            'proposal': 'sampleproposal', 'filter': 'opaque', 'instrument_type': 'SOAR_GHTS_REDCAM_IMAGER'
        }
        self.instrument_choices = [(k, v['name']) for k, v in instrument_response.items() if 'SOAR' in k]
        self.filter_choices = set([
            (f['code'], f['name']) for ins in instrument_response.values() for f in
            ins['optical_elements'].get('filters', []) + ins['optical_elements'].get('slits', [])
        ])
        self.proposal_choices = [('sampleproposal', 'Sample Proposal')]

    @patch('tom_observations.facilities.soar.make_request')
    @patch('tom_observations.facilities.soar.cache')
    def test_get_instruments(self, mock_cache, mock_make_request):
        mock_response = Response()
        mock_response._content = str.encode(json.dumps(instrument_response))
        mock_response.status_code = 200
        mock_make_request.return_value = mock_response

        # Test that cached value is returned
        with self.subTest():
            test_instruments = {'test instrument': {'type': 'IMAGE'}}
            mock_cache.get.return_value = test_instruments

            instruments = SOARBaseObservationForm._get_instruments()
            self.assertDictContainsSubset({'test instrument': {'type': 'IMAGE'}}, instruments)
            self.assertNotIn('0M4-SCICAM-SBIG', instruments)

        # Test that empty cache results in mock_instruments, and cache.set is called
        with self.subTest():
            mock_cache.get.return_value = None

            instruments = SOARBaseObservationForm._get_instruments()
            self.assertIn('SOAR_GHTS_REDCAM_IMAGER', instruments)
            self.assertDictContainsSubset({'type': 'IMAGE'}, instruments['SOAR_GHTS_REDCAM_IMAGER'])
            self.assertNotIn('0M4-SCICAM-SBIG', instruments)
            mock_cache.set.assert_called()

    @patch('tom_observations.facilities.soar.SOARBaseObservationForm.proposal_choices')
    @patch('tom_observations.facilities.soar.SOARBaseObservationForm.filter_choices')
    @patch('tom_observations.facilities.soar.SOARBaseObservationForm.instrument_choices')
    @patch('tom_observations.facilities.soar.SOARBaseObservationForm.validate_at_facility')
    def test_instrument_to_type(self, mock_validate, mock_insts, mock_filters, mock_proposals):
        """Test instrument_to_type method."""
        self.assertEqual('EXPOSE', SOARBaseObservationForm.instrument_to_type('SOAR_GHTS_REDCAM_IMAGER'))
        self.assertEqual('SPECTRUM', SOARBaseObservationForm.instrument_to_type('SOAR_GHTS_REDCAM'))


@patch('tom_observations.facilities.soar.SOARImagingObservationForm._get_instruments')
class TestSOARImagingObservationForm(TestCase):
    def test_instrument_choices(self, mock_get_instruments):
        """Test SOARImagingObservationForm._instrument_choices."""
        mock_get_instruments.return_value = {k: v for k, v in instrument_response.items() if 'SOAR' in k}

        inst_choices = SOARImagingObservationForm.instrument_choices()
        self.assertIn(('SOAR_GHTS_REDCAM_IMAGER', 'Goodman Spectrograph RedCam Imager'), inst_choices)
        self.assertNotIn(('SOAR_GHTS_REDCAM', 'Goodman Spectrograph RedCam'), inst_choices)
        self.assertEqual(len(inst_choices), 1)

    def test_filter_choices(self, mock_get_instruments):
        """Test SOARImagingObservationForm._filter_choices."""
        mock_get_instruments.return_value = {k: v for k, v in instrument_response.items() if 'SOAR' in k}

        filter_choices = SOARImagingObservationForm.filter_choices()
        for expected in [('air', 'Clear'), ('u-SDSS', 'GHTS u-SDSS'), ('g-SDSS', 'GHTS g-SDSS'),
                         ('r-SDSS', 'GHTS r-SDSS'), ('i-SDSS', 'GHTS i-SDSS'), ('z-SDSS', 'GHTS z-SDSS'),
                         ('VR', 'GHTS VR')]:
            self.assertIn(expected, filter_choices)
        for not_expected in [('slit_1.0as', '1.0 arcsec slit')]:
            self.assertNotIn(not_expected, filter_choices)
        self.assertEqual(len(filter_choices), 7)


class TestSOARSpectroscopyObservationForm(TestCase):

    @patch('tom_observations.facilities.soar.SOARSpectroscopyObservationForm._get_instruments')
    def test_instrument_choices(self, mock_get_instruments):
        """Test SOARSpectroscopyObservationForm._instrument_choices."""
        mock_get_instruments.return_value = {k: v for k, v in instrument_response.items() if 'SOAR' in k}

        inst_choices = SOARSpectroscopyObservationForm.instrument_choices()
        self.assertIn(('SOAR_GHTS_REDCAM', 'Goodman Spectrograph RedCam'), inst_choices)
        self.assertNotIn(('SOAR_GHTS_REDCAM_IMAGER', 'Goodman Spectrograph RedCam Imager'), inst_choices)
        self.assertEqual(len(inst_choices), 1)

    @patch('tom_observations.facilities.soar.SOARSpectroscopyObservationForm._get_instruments')
    def test_filter_choices(self, mock_get_instruments):
        """Test SOARSpectroscopyObservationForm._filter_choices."""
        mock_get_instruments.return_value = {k: v for k, v in instrument_response.items() if 'SOAR' in k}

        filter_choices = SOARSpectroscopyObservationForm.filter_choices()
        for expected in [('slit_1.0as', '1.0 arcsec slit')]:
            self.assertIn(expected, filter_choices)
        for not_expected in [('u-SDSS', 'GHTS u-SDSS'), ('i-SDSS', 'GHTS i-SDSS')]:
            self.assertNotIn(not_expected, filter_choices)
        self.assertEqual(len(filter_choices), 1)

    @patch('tom_observations.facilities.soar.SOARSpectroscopyObservationForm.proposal_choices')
    @patch('tom_observations.facilities.soar.SOARSpectroscopyObservationForm.filter_choices')
    @patch('tom_observations.facilities.soar.SOARSpectroscopyObservationForm.instrument_choices')
    @patch('tom_observations.facilities.soar.SOARSpectroscopyObservationForm.validate_at_facility')
    def test_build_instrument_config(self, mock_validate, mock_insts, mock_filters, mock_proposals):
        mock_validate.return_value = []
        mock_insts.return_value = [(k, v['name']) for k, v in instrument_response.items() if 'SPECTRA' in v['type']]
        mock_filters.return_value = set([
            (f['code'], f['name']) for ins in instrument_response.values() for f in
            ins['optical_elements'].get('slits', [])
            ] + [('None', 'None')])
        mock_proposals.return_value = [('sampleproposal', 'Sample Proposal')]

        st = SiderealTargetFactory.create()
        valid_form_data = {
            'name': 'test', 'facility': 'SOAR', 'target_id': st.id, 'ipp_value': 0.5, 'start': '2020-11-03',
            'end': '2020-11-04', 'exposure_count': 1, 'exposure_time': 30.0, 'max_airmass': 3,
            'min_lunar_distance': 20, 'observation_mode': 'NORMAL', 'proposal': 'sampleproposal',
            'filter': 'slit_1.0as', 'instrument_type': 'SOAR_GHTS_REDCAM', 'rotator_angle': 1.0
        }

        # Test that optical_elements['slit'] and optical_elements['grating] are populated when filter is included
        with self.subTest():
            form = SOARSpectroscopyObservationForm(valid_form_data)
            self.assertTrue(form.is_valid())
            self.assertEqual(
                [{'exposure_count': valid_form_data['exposure_count'],
                  'exposure_time': valid_form_data['exposure_time'],
                  'optical_elements': {'slit': valid_form_data['filter'], 'grating': 'SYZY_400'},
                  'rotator_mode': 'SKY',
                  'extra_params': {'rotator_angle': valid_form_data['rotator_angle']}
                  }], form._build_instrument_config()
            )
