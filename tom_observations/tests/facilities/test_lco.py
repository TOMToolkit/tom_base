import json
from requests import Response
from unittest.mock import patch

from django.test import TestCase

from tom_common.exceptions import ImproperCredentialsException
from tom_observations.facilities.lco import make_request
from tom_observations.facilities.lco import LCOBaseForm, LCOBaseObservationForm
from tom_observations.tests.factories import SiderealTargetFactory, NonSiderealTargetFactory


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

        mock_response.status_code = 403
        mock_request.return_value = mock_response
        with self.assertRaises(ImproperCredentialsException):
            make_request('GET', 'google.com', headers={'test': 'test'})


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
        mock_response._content = str.encode(json.dumps({'proposals': [
            {'id': 'ActiveProposal', 'title': 'Active', 'current': True},
            {'id': 'InactiveProposal', 'title': 'Inactive', 'current': False}]
        }))
        mock_response.status_code = 200
        mock_make_request.return_value = mock_response

        proposal_choices = LCOBaseForm.proposal_choices()
        self.assertIn(('ActiveProposal', 'Active (ActiveProposal)'), proposal_choices)
        self.assertNotIn(('InactiveProposal', 'Inactive (InactiveProposal)'), proposal_choices)


@patch('tom_observations.facilities.lco.LCOBaseForm.proposal_choices')
@patch('tom_observations.facilities.lco.LCOBaseForm.filter_choices')
@patch('tom_observations.facilities.lco.LCOBaseForm.instrument_choices')
@patch('tom_observations.facilities.lco.LCOBaseObservationForm.validate_at_facility')
class TestLCOBaseObservationFormPayload(TestCase):

    def setUp(self):
        self.st = SiderealTargetFactory.create()
        self.nst = NonSiderealTargetFactory.create(scheme='MPC_MINOR_PLANET')
        self.valid_form_data = {
            'name': 'test', 'facility': 'LCO', 'target_id': self.st.id, 'ipp_value': 0.5, 'start': '2020-11-03',
            'end': '2020-11-04', 'exposure_count': 1, 'exposure_time': 30, 'max_airmass': 3,
            'min_lunar_distance': 20, 'period': 60, 'jitter': 15, 'observation_mode': 'NORMAL',
            'proposal': 'sampleproposal', 'filter': 'opaque', 'instrument_type': '0M4-SCICAM-SBIG'
        }
        self.instrument_choices = [(k, v['name']) for k, v in instrument_response.items() if 'SOAR' not in k]
        self.filter_choices = set([
            (f['code'], f['name']) for ins in instrument_response.values() for f in
            ins['optical_elements'].get('filters', []) + ins['optical_elements'].get('slits', [])
        ])
        self.proposal_choices = [('sampleproposal', 'Sample Proposal')]

    def test_clean_and_validate(self, mock_validate, mock_insts, mock_filters, mock_proposals):
        """Test clean_start, clean_end, and is_valid()"""
        mock_validate.return_value = []
        mock_insts.return_value = self.instrument_choices
        mock_filters.return_value = self.filter_choices
        mock_proposals.return_value = self.proposal_choices

        # Test that a valid form returns True, and that start and end are cleaned properly
        form = LCOBaseObservationForm(self.valid_form_data)
        self.assertTrue(form.is_valid())
        self.assertEqual('2020-11-03T00:00:00', form.cleaned_data['start'])
        self.assertEqual('2020-11-04T00:00:00', form.cleaned_data['end'])

        # Test that an invalid form returns False
        self.valid_form_data.pop('target_id')
        form = LCOBaseObservationForm(self.valid_form_data)
        self.assertFalse(form.is_valid())

        # TODO: Add test for when validate_at_facility returns errors

    def test_flatten_error_dict(self, mock_validate, mock_insts, mock_filters, mock_proposals):
        pass

    def test_instrument_to_type(self, mock_validate, mock_insts, mock_filters, mock_proposals):
        """Test instrument_to_type method."""
        self.assertEqual('SPECTRUM', LCOBaseObservationForm.instrument_to_type('2M0-FLOYDS-SCICAM'))
        self.assertEqual('NRES_SPECTRUM', LCOBaseObservationForm.instrument_to_type('1M0-NRES-SCICAM'))
        self.assertEqual('EXPOSE', LCOBaseObservationForm.instrument_to_type('0M4-SCICAM-SBIG'))

    def test_build_target_fields(self, mock_validate, mock_insts, mock_filters, mock_proposals):
        """Test _build_target_fields method."""
        mock_validate.return_value = []
        mock_insts.return_value = self.instrument_choices
        mock_filters.return_value = self.filter_choices
        mock_proposals.return_value = self.proposal_choices

        # Test correct population of target fields for a sidereal target
        with self.subTest():
            form = LCOBaseObservationForm(self.valid_form_data)
            self.assertTrue(form.is_valid())
            self.assertDictEqual({
                'name': self.st.name, 'type': 'ICRS', 'ra': self.st.ra, 'dec': self.st.dec,
                'proper_motion_ra': self.st.pm_ra, 'proper_motion_dec': self.st.pm_dec, 'epoch': self.st.epoch
            }, form._build_target_fields())

        # Test correct population of target fields for a non-sidereal target
        with self.subTest():
            self.valid_form_data['target_id'] = self.nst.id
            form = LCOBaseObservationForm(self.valid_form_data)
            self.assertTrue(form.is_valid())
            self.assertDictContainsSubset({
                'name': self.nst.name, 'type': 'ORBITAL_ELEMENTS', 'epochofel': self.nst.epoch_of_elements,
                'orbinc': self.nst.inclination, 'longascnode': self.nst.lng_asc_node,
                'argofperih': self.nst.arg_of_perihelion, 'meananom': self.nst.mean_anomaly,
                'meandist': self.nst.semimajor_axis
            }, form._build_target_fields())

    def test_build_instrument_config(self, mock_validate, mock_insts, mock_filters, mock_proposals):
        """Test _build_instrument_config method."""
        mock_validate.return_value = []
        mock_insts.return_value = self.instrument_choices
        mock_filters.return_value = self.filter_choices
        mock_proposals.return_value = self.proposal_choices

        form = LCOBaseObservationForm(self.valid_form_data)
        self.assertTrue(form.is_valid())
        self.assertEqual(
            [{'exposure_count': self.valid_form_data['exposure_count'],
              'exposure_time': self.valid_form_data['exposure_time'],
              'optical_elements': {'filter': self.valid_form_data['filter']}
              }],
            form._build_instrument_config()
        )

    def test_build_acquisition_config(self, mock_validate, mock_insts, mock_filters, mock_proposals):
        """Test _build_acquisition_config method."""
        mock_validate.return_value = []
        mock_insts.return_value = self.instrument_choices
        mock_filters.return_value = self.filter_choices
        mock_proposals.return_value = self.proposal_choices

        form = LCOBaseObservationForm(self.valid_form_data)
        self.assertTrue(form.is_valid())
        self.assertDictEqual({}, form._build_acquisition_config())

    def test_build_guiding_config(self, mock_validate, mock_insts, mock_filters, mock_proposals):
        """Test _build_guiding_config method."""
        mock_validate.return_value = []
        mock_insts.return_value = self.instrument_choices
        mock_filters.return_value = self.filter_choices
        mock_proposals.return_value = self.proposal_choices

        form = LCOBaseObservationForm(self.valid_form_data)
        self.assertTrue(form.is_valid())
        self.assertDictEqual({}, form._build_guiding_config())

    # This should but does not mock instrument_to_type, _build_target_fields, _build_instrument_config,
    # _build_acquisition_config, and _build_guiding_config
    def test_build_configuration(self, mock_validate, mock_insts, mock_filters, mock_proposals):
        """Test _build_configuration method."""
        mock_validate.return_value = []
        mock_insts.return_value = self.instrument_choices
        mock_filters.return_value = self.filter_choices
        mock_proposals.return_value = self.proposal_choices

        form = LCOBaseObservationForm(self.valid_form_data)
        self.assertTrue(form.is_valid())
        configuration = form._build_configuration()
        self.assertDictContainsSubset(
            {'type': 'EXPOSE', 'instrument_type': '0M4-SCICAM-SBIG', 'constraints': {'max_airmass': 3}},
            configuration)
        for key in ['target', 'instrument_configs', 'acquisition_config', 'guiding_config']:
            self.assertIn(key, configuration)

    @patch('tom_observations.facilities.lco.LCOBaseForm._get_instruments')
    def test_build_location(self, mock_get_instruments, mock_validate, mock_insts, mock_filters, mock_proposals):
        """Test _build_location method."""
        mock_get_instruments.return_value = {k: v for k, v in instrument_response.items() if 'SOAR' not in k}
        mock_validate.return_value = []
        mock_insts.return_value = self.instrument_choices
        mock_filters.return_value = self.filter_choices
        mock_proposals.return_value = self.proposal_choices

        form = LCOBaseObservationForm(self.valid_form_data)
        self.assertTrue(form.is_valid())
        self.assertDictEqual({'telescope_class': '0m4'}, form._build_location())

    def test_expand_cadence_request(self, mock_validate, mock_insts, mock_filters, mock_proposals):
        pass

    def test_observation_payload(self, mock_validate, mock_insts, mock_filters, mock_proposals):
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
