from datetime import datetime, timedelta
import json
from requests import Response
from unittest.mock import patch

from django.test import TestCase

from tom_common.exceptions import ImproperCredentialsException
from tom_observations.facilities.lco import make_request
from tom_observations.facilities.lco import LCOBaseForm, LCOBaseObservationForm, LCOImagingObservationForm
from tom_observations.facilities.lco import LCOPhotometricSequenceForm, LCOSpectroscopicSequenceForm
from tom_observations.facilities.lco import LCOSpectroscopyObservationForm
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
        self.assertEqual(len(inst_choices), 2)

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


@patch('tom_observations.facilities.lco.LCOBaseObservationForm.proposal_choices')
@patch('tom_observations.facilities.lco.LCOBaseObservationForm.filter_choices')
@patch('tom_observations.facilities.lco.LCOBaseObservationForm.instrument_choices')
@patch('tom_observations.facilities.lco.LCOBaseObservationForm.validate_at_facility')
class TestLCOBaseObservationForm(TestCase):

    def setUp(self):
        self.st = SiderealTargetFactory.create()
        self.nst = NonSiderealTargetFactory.create(scheme='MPC_MINOR_PLANET')
        self.valid_form_data = {
            'name': 'test', 'facility': 'LCO', 'target_id': self.st.id, 'ipp_value': 0.5, 'start': '2020-11-03',
            'end': '2020-11-04', 'exposure_count': 1, 'exposure_time': 30, 'max_airmass': 3,
            'min_lunar_distance': 20, 'observation_mode': 'NORMAL',
            'proposal': 'sampleproposal', 'filter': 'opaque', 'instrument_type': '0M4-SCICAM-SBIG'
        }
        self.instrument_choices = [(k, v['name']) for k, v in instrument_response.items() if 'SOAR' not in k]
        self.filter_choices = set([
            (f['code'], f['name']) for ins in instrument_response.values() for f in
            ins['optical_elements'].get('filters', []) + ins['optical_elements'].get('slits', [])
        ])
        self.proposal_choices = [('sampleproposal', 'Sample Proposal')]

    def test_validate_at_facility(self, mock_validate, mock_insts, mock_filters, mock_proposals):
        pass

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

    @patch('tom_observations.facilities.lco.LCOBaseObservationForm._build_location')
    @patch('tom_observations.facilities.lco.LCOBaseObservationForm._build_configuration')
    @patch('tom_observations.facilities.lco.make_request')
    def test_observation_payload(self, mock_make_request, mock_build_configuration, mock_build_location, mock_validate,
                                 mock_insts, mock_filters, mock_proposals):
        """Test observation_payload method."""
        mock_build_configuration.return_value = {}
        mock_build_location.return_value = {}
        mock_validate.return_value = []
        mock_insts.return_value = self.instrument_choices
        mock_filters.return_value = self.filter_choices
        mock_proposals.return_value = self.proposal_choices

        # Test a non-static cadenced form
        with self.subTest():
            form = LCOBaseObservationForm(self.valid_form_data)
            self.assertTrue(form.is_valid())
            obs_payload = form.observation_payload()
            self.assertDictContainsSubset(
                {'name': 'test', 'proposal': 'sampleproposal', 'ipp_value': 0.5, 'operator': 'SINGLE',
                 'observation_type': 'NORMAL'}, obs_payload
            )
            self.assertNotIn('cadence', obs_payload['requests'][0])

        # Test a static cadence form
        with self.subTest():
            mock_response = Response()
            mock_response._content = str.encode(json.dumps({'test': 'test_static_cadence'}))
            mock_response.status_code = 200
            mock_make_request.return_value = mock_response

            self.valid_form_data['period'] = 60
            self.valid_form_data['jitter'] = 15
            form = LCOBaseObservationForm(self.valid_form_data)
            self.assertTrue(form.is_valid())
            self.assertDictEqual({'test': 'test_static_cadence'}, form.observation_payload())


@patch('tom_observations.facilities.lco.LCOImagingObservationForm._get_instruments')
class TestLCOImagingObservationForm(TestCase):
    def test_instrument_choices(self, mock_get_instruments):
        """Test LCOImagingObservationForm._instrument_choices."""
        mock_get_instruments.return_value = {k: v for k, v in instrument_response.items() if 'SOAR' not in k}

        inst_choices = LCOImagingObservationForm.instrument_choices()
        self.assertIn(('0M4-SCICAM-SBIG', '0.4 meter SBIG'), inst_choices)
        self.assertNotIn(('2M0-FLOYDS-SCICAM', '2.0 meter FLOYDS'), inst_choices)
        self.assertEqual(len(inst_choices), 1)

    def test_filter_choices(self, mock_get_instruments):
        """Test LCOImagingObservationForm._filter_choices."""
        mock_get_instruments.return_value = {k: v for k, v in instrument_response.items() if 'SOAR' not in k}

        filter_choices = LCOImagingObservationForm.filter_choices()
        for expected in [('opaque', 'Opaque'), ('100um-Pinhole', '100um Pinhole')]:
            self.assertIn(expected, filter_choices)
        for not_expected in [('slit_6.0as', '6.0 arcsec slit'), ('slit_1.6as', '1.6 arcsec slit'),
                             ('slit_2.0as', '2.0 arcsec slit'), ('slit_1.2as', '1.2 arcsec slit')]:
            self.assertNotIn(not_expected, filter_choices)
        self.assertEqual(len(filter_choices), 2)


class TestLCOSpectroscopyObservationForm(TestCase):
    @patch('tom_observations.facilities.lco.LCOSpectroscopyObservationForm._get_instruments')
    def test_instrument_choices(self, mock_get_instruments):
        """Test LCOSpectroscopyObservationForm._instrument_choices."""
        mock_get_instruments.return_value = {k: v for k, v in instrument_response.items() if 'SOAR' not in k}

        inst_choices = LCOSpectroscopyObservationForm.instrument_choices()
        self.assertIn(('2M0-FLOYDS-SCICAM', '2.0 meter FLOYDS'), inst_choices)
        self.assertNotIn(('0M4-SCICAM-SBIG', '0.4 meter SBIG'), inst_choices)
        self.assertEqual(len(inst_choices), 1)

    @patch('tom_observations.facilities.lco.LCOSpectroscopyObservationForm._get_instruments')
    def test_filter_choices(self, mock_get_instruments):
        """Test LCOSpectroscopyObservationForm._filter_choices."""
        mock_get_instruments.return_value = {k: v for k, v in instrument_response.items() if 'SOAR' not in k}

        filter_choices = LCOSpectroscopyObservationForm.filter_choices()
        for expected in [('slit_6.0as', '6.0 arcsec slit'), ('slit_1.6as', '1.6 arcsec slit'),
                         ('slit_2.0as', '2.0 arcsec slit'), ('slit_1.2as', '1.2 arcsec slit'), ('None', 'None')]:
            self.assertIn(expected, filter_choices)
        for not_expected in [('opaque', 'Opaque'), ('100um-Pinhole', '100um Pinhole')]:
            self.assertNotIn(not_expected, filter_choices)
        self.assertEqual(len(filter_choices), 5)

    @patch('tom_observations.facilities.lco.LCOSpectroscopyObservationForm.proposal_choices')
    @patch('tom_observations.facilities.lco.LCOSpectroscopyObservationForm.filter_choices')
    @patch('tom_observations.facilities.lco.LCOSpectroscopyObservationForm.instrument_choices')
    @patch('tom_observations.facilities.lco.LCOSpectroscopyObservationForm.validate_at_facility')
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
            'name': 'test', 'facility': 'LCO', 'target_id': st.id, 'ipp_value': 0.5, 'start': '2020-11-03',
            'end': '2020-11-04', 'exposure_count': 1, 'exposure_time': 30.0, 'max_airmass': 3,
            'min_lunar_distance': 20, 'observation_mode': 'NORMAL', 'proposal': 'sampleproposal',
            'filter': 'slit_2.0as', 'instrument_type': '2M0-FLOYDS-SCICAM', 'rotator_angle': 1.0
        }

        # Test that optical_elements['slit'] is populated when filter is included
        with self.subTest():
            form = LCOSpectroscopyObservationForm(valid_form_data)
            self.assertTrue(form.is_valid())
            self.assertEqual(
                [{'exposure_count': valid_form_data['exposure_count'],
                  'exposure_time': valid_form_data['exposure_time'],
                  'optical_elements': {'slit': valid_form_data['filter']},
                  'rotator_mode': 'VFLOAT',
                  'extra_params': {'rotator_angle': valid_form_data['rotator_angle']}
                  }], form._build_instrument_config()
            )

        # Test that optical elements is removed when filter is excluded
        with self.subTest():
            valid_form_data['filter'] = 'None'
            form = LCOSpectroscopyObservationForm(valid_form_data)
            self.assertTrue(form.is_valid())
            self.assertEqual(
                [{'exposure_count': valid_form_data['exposure_count'],
                  'exposure_time': valid_form_data['exposure_time'],
                  'rotator_mode': 'VFLOAT', 'extra_params': {'rotator_angle': valid_form_data['rotator_angle']}
                  }], form._build_instrument_config()
            )


class TestLCOPhotometricSequenceForm(TestCase):

    def setUp(self):
        self.st = SiderealTargetFactory.create()
        self.valid_form_data = {
            'name': 'test', 'facility': 'LCO', 'target_id': self.st.id, 'ipp_value': 0.5, 'max_airmass': 3,
            'min_lunar_distance': 20, 'observation_mode': 'NORMAL', 'proposal': 'sampleproposal',
            'instrument_type': '0M4-SCICAM-SBIG', 'cadence_frequency': 24,
            'U_0': 30.0, 'U_1': 1, 'U_2': 1, 'B_0': 60.0, 'B_1': 2, 'B_2': 1,
        }
        self.instrument_choices = [(k, v['name']) for k, v in instrument_response.items() if 'SOAR' not in k]
        self.filter_choices = set([
            (f['code'], f['name']) for ins in instrument_response.values() for f in
            ins['optical_elements'].get('filters', []) + ins['optical_elements'].get('slits', [])
        ])
        self.proposal_choices = [('sampleproposal', 'Sample Proposal')]

    @patch('tom_observations.facilities.lco.LCOPhotometricSequenceForm._get_instruments')
    def test_instrument_choices(self, mock_get_instruments):
        """Test LCOPhotometricSequenceForm._instrument_choices."""
        mock_get_instruments.return_value = {k: v for k, v in instrument_response.items() if 'SOAR' not in k}

        inst_choices = LCOPhotometricSequenceForm.instrument_choices()
        self.assertIn(('0M4-SCICAM-SBIG', '0.4 meter SBIG'), inst_choices)
        self.assertNotIn(('2M0-FLOYDS-SCICAM', '2.0 meter FLOYDS'), inst_choices)
        self.assertEqual(len(inst_choices), 1)

    @patch('tom_observations.facilities.lco.LCOPhotometricSequenceForm.proposal_choices')
    @patch('tom_observations.facilities.lco.LCOPhotometricSequenceForm.filter_choices')
    @patch('tom_observations.facilities.lco.LCOPhotometricSequenceForm.instrument_choices')
    @patch('tom_observations.facilities.lco.LCOPhotometricSequenceForm.validate_at_facility')
    def test_build_instrument_config(self, mock_validate, mock_insts, mock_filters, mock_proposals):
        mock_validate.return_value = []
        mock_insts.return_value = self.instrument_choices
        mock_filters.return_value = self.filter_choices
        mock_proposals.return_value = self.proposal_choices

        form = LCOPhotometricSequenceForm(self.valid_form_data)
        self.assertTrue(form.is_valid())
        inst_config = form._build_instrument_config()
        self.assertEqual(len(inst_config), 2)
        self.assertIn({'exposure_count': 1, 'exposure_time': 30.0, 'optical_elements': {'filter': 'U'}}, inst_config)
        self.assertIn({'exposure_count': 2, 'exposure_time': 60.0, 'optical_elements': {'filter': 'B'}}, inst_config)

    @patch('tom_observations.facilities.lco.LCOPhotometricSequenceForm.proposal_choices')
    @patch('tom_observations.facilities.lco.LCOPhotometricSequenceForm.filter_choices')
    @patch('tom_observations.facilities.lco.LCOPhotometricSequenceForm.instrument_choices')
    @patch('tom_observations.facilities.lco.LCOPhotometricSequenceForm.validate_at_facility')
    def test_clean(self, mock_validate, mock_insts, mock_filters, mock_proposals):
        mock_validate.return_value = []
        mock_insts.return_value = self.instrument_choices
        mock_filters.return_value = self.filter_choices
        mock_proposals.return_value = self.proposal_choices

        # Test that a valid form returns True, and that start and end are cleaned properly
        form = LCOPhotometricSequenceForm(self.valid_form_data)
        self.assertTrue(form.is_valid())
        self.assertAlmostEqual(datetime.strftime(datetime.now(), '%Y-%m-%dT%H:%M:%S'), form.cleaned_data['start'])
        self.assertAlmostEqual(
            datetime.strftime(
                datetime.now() + timedelta(hours=form.cleaned_data['cadence_frequency']), '%Y-%m-%dT%H:%M:%S'
            ),
            form.cleaned_data['end']
        )

        # Test that an invalid form returns False
        self.valid_form_data.pop('target_id')
        form = LCOPhotometricSequenceForm(self.valid_form_data)
        self.assertFalse(form.is_valid())


class TestLCOSpectroscopicSequenceForm(TestCase):
    def setUp(self):
        self.st = SiderealTargetFactory.create()
        self.valid_form_data = {
            'name': 'test', 'facility': 'LCO', 'target_id': self.st.id, 'exposure_count': 1, 'exposure_time': 30,
            'max_airmass': 3, 'min_lunar_distance': 20, 'site': 'any', 'ipp_value': 0.5, 'filter': 'slit_1.2as',
            'observation_mode': 'NORMAL', 'proposal': 'sampleproposal', 'acquisition_radius': 1,
            'guider_mode': 'on', 'guider_exposure_time': 30, 'instrument_type': '0M4-SCICAM-SBIG',
            'cadence_frequency': 24
        }
        self.instrument_choices = [(k, v['name']) for k, v in instrument_response.items() if 'SOAR' not in k]
        self.filter_choices = set([
            (f['code'], f['name']) for ins in instrument_response.values() for f in
            ins['optical_elements'].get('filters', []) + ins['optical_elements'].get('slits', [])
        ])
        self.proposal_choices = [('sampleproposal', 'Sample Proposal')]

    @patch('tom_observations.facilities.lco.LCOSpectroscopicSequenceForm._get_instruments')
    def test_instrument_choices(self, mock_get_instruments):
        """Test LCOSpectroscopicSequenceForm._instrument_choices."""
        mock_get_instruments.return_value = {k: v for k, v in instrument_response.items() if 'SOAR' not in k}

        inst_choices = LCOSpectroscopicSequenceForm.instrument_choices()
        self.assertIn(('2M0-FLOYDS-SCICAM', '2.0 meter FLOYDS'), inst_choices)
        self.assertNotIn(('0M4-SCICAM-SBIG', '0.4 meter SBIG'), inst_choices)
        self.assertEqual(len(inst_choices), 1)

    @patch('tom_observations.facilities.lco.LCOSpectroscopicSequenceForm._get_instruments')
    def test_filter_choices(self, mock_get_instruments):
        """Test LCOSpectroscopicSequenceForm._instrument_choices."""
        mock_get_instruments.return_value = {k: v for k, v in instrument_response.items() if 'SOAR' not in k}

        filter_choices = LCOSpectroscopicSequenceForm.filter_choices()
        for expected in [('slit_6.0as', '6.0 arcsec slit'), ('slit_1.6as', '1.6 arcsec slit'),
                         ('slit_2.0as', '2.0 arcsec slit'), ('slit_1.2as', '1.2 arcsec slit')]:
            self.assertIn(expected, filter_choices)
        for not_expected in [('opaque', 'Opaque'), ('100um-Pinhole', '100um Pinhole')]:
            self.assertNotIn(not_expected, filter_choices)
        self.assertEqual(len(filter_choices), 4)

    @patch('tom_observations.facilities.lco.LCOSpectroscopicSequenceForm.proposal_choices')
    @patch('tom_observations.facilities.lco.LCOSpectroscopicSequenceForm.filter_choices')
    @patch('tom_observations.facilities.lco.LCOSpectroscopicSequenceForm.instrument_choices')
    @patch('tom_observations.facilities.lco.LCOSpectroscopicSequenceForm.validate_at_facility')
    def test_build_instrument_config(self, mock_validate, mock_insts, mock_filters, mock_proposals):
        mock_validate.return_value = []
        mock_insts.return_value = self.instrument_choices
        mock_filters.return_value = self.filter_choices
        mock_proposals.return_value = self.proposal_choices

        form = LCOSpectroscopicSequenceForm(self.valid_form_data)
        self.assertTrue(form.is_valid())
        inst_config = form._build_instrument_config()
        self.assertEqual(len(inst_config), 1)
        self.assertIn({'exposure_count': 1, 'exposure_time': 30.0, 'optical_elements': {'slit': 'slit_1.2as'}},
                      inst_config)
        self.assertNotIn('filter', inst_config[0]['optical_elements'])

    @patch('tom_observations.facilities.lco.LCOSpectroscopicSequenceForm.proposal_choices')
    @patch('tom_observations.facilities.lco.LCOSpectroscopicSequenceForm.filter_choices')
    @patch('tom_observations.facilities.lco.LCOSpectroscopicSequenceForm.instrument_choices')
    @patch('tom_observations.facilities.lco.LCOSpectroscopicSequenceForm.validate_at_facility')
    def test_build_acquisition_config(self, mock_validate, mock_insts, mock_filters, mock_proposals):
        mock_validate.return_value = []
        mock_insts.return_value = self.instrument_choices
        mock_filters.return_value = self.filter_choices
        mock_proposals.return_value = self.proposal_choices

        with self.subTest():
            form = LCOSpectroscopicSequenceForm(self.valid_form_data)
            self.assertTrue(form.is_valid())
            acquisition_config = form._build_acquisition_config()
            self.assertDictEqual({'mode': 'BRIGHTEST', 'extra_params': {'acquire_radius': 1}},
                                 acquisition_config)

        with self.subTest():
            self.valid_form_data.pop('acquisition_radius')
            form = LCOSpectroscopicSequenceForm(self.valid_form_data)
            self.assertTrue(form.is_valid())
            acquisition_config = form._build_acquisition_config()
            self.assertDictEqual({'mode': 'WCS'}, acquisition_config)

    @patch('tom_observations.facilities.lco.LCOSpectroscopicSequenceForm.proposal_choices')
    @patch('tom_observations.facilities.lco.LCOSpectroscopicSequenceForm.filter_choices')
    @patch('tom_observations.facilities.lco.LCOSpectroscopicSequenceForm.instrument_choices')
    @patch('tom_observations.facilities.lco.LCOSpectroscopicSequenceForm.validate_at_facility')
    def test_build_guiding_config(self, mock_validate, mock_insts, mock_filters, mock_proposals):
        mock_validate.return_value = []
        mock_insts.return_value = self.instrument_choices
        mock_filters.return_value = self.filter_choices
        mock_proposals.return_value = self.proposal_choices

        test_params = [
            ({'guider_mode': 'on'}, {'mode': 'ON', 'optional': 'false'}),
            ({'guider_mode': 'off'}, {'mode': 'OFF', 'optional': 'false'}),
            ({'guider_mode': 'optional'}, {'mode': 'ON', 'optional': 'true'})
        ]
        for params in test_params:
            with self.subTest():
                self.valid_form_data.update(params[0])
                form = LCOSpectroscopicSequenceForm(self.valid_form_data)
                self.assertTrue(form.is_valid())
                guiding_config = form._build_guiding_config()
                self.assertDictEqual(params[1], guiding_config)

    @patch('tom_observations.facilities.lco.LCOSpectroscopicSequenceForm.proposal_choices')
    @patch('tom_observations.facilities.lco.LCOSpectroscopicSequenceForm.filter_choices')
    @patch('tom_observations.facilities.lco.LCOSpectroscopicSequenceForm.instrument_choices')
    @patch('tom_observations.facilities.lco.LCOSpectroscopicSequenceForm.validate_at_facility')
    @patch('tom_observations.facilities.lco.LCOSpectroscopicSequenceForm._get_instruments')
    def test_build_location(self, mock_get_instruments, mock_validate, mock_insts, mock_filters, mock_proposals):
        mock_get_instruments.return_value = {k: v for k, v in instrument_response.items() if 'SOAR' not in k}
        mock_validate.return_value = []
        mock_insts.return_value = self.instrument_choices
        mock_filters.return_value = self.filter_choices
        mock_proposals.return_value = self.proposal_choices

        test_params = [
            ({'site': 'ogg'}, {'site': 'ogg'}),
            ({'site': 'coj'}, {'site': 'coj'}),
            ({'site': 'any'}, {})
        ]
        for params in test_params:
            with self.subTest():
                self.valid_form_data.update(params[0])
                form = LCOSpectroscopicSequenceForm(self.valid_form_data)
                self.assertTrue(form.is_valid())
                location = form._build_location()
                self.assertDictContainsSubset(params[1], location)

    @patch('tom_observations.facilities.lco.LCOSpectroscopicSequenceForm.proposal_choices')
    @patch('tom_observations.facilities.lco.LCOSpectroscopicSequenceForm.filter_choices')
    @patch('tom_observations.facilities.lco.LCOSpectroscopicSequenceForm.instrument_choices')
    @patch('tom_observations.facilities.lco.LCOSpectroscopicSequenceForm.validate_at_facility')
    def test_clean(self, mock_validate, mock_insts, mock_filters, mock_proposals):
        mock_validate.return_value = []
        mock_insts.return_value = self.instrument_choices
        mock_filters.return_value = self.filter_choices
        mock_proposals.return_value = self.proposal_choices

        # Test that a valid form returns True, and that start and end are cleaned properly
        form = LCOSpectroscopicSequenceForm(self.valid_form_data)
        self.assertTrue(form.is_valid())
        self.assertEqual(form.cleaned_data['instrument_type'], '2M0-FLOYDS-SCICAM')
        self.assertAlmostEqual(datetime.strftime(datetime.now(), '%Y-%m-%dT%H:%M:%S'), form.cleaned_data['start'])
        self.assertAlmostEqual(
            datetime.strftime(
                datetime.now() + timedelta(hours=form.cleaned_data['cadence_frequency']), '%Y-%m-%dT%H:%M:%S'
            ),
            form.cleaned_data['end']
        )

        # Test that an invalid form returns False
        self.valid_form_data.pop('target_id')
        form = LCOSpectroscopicSequenceForm(self.valid_form_data)
        self.assertFalse(form.is_valid())


class TestLCOObservationTemplateForm(TestCase):
    pass


class TestLCOFacility(TestCase):
    pass
