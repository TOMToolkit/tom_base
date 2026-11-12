from datetime import timedelta
from unittest.mock import patch

from aeonlib.ocs.request_models import RequestGroup, ValidationResult
from aeonlib.utils.django import PydanticValidationMixin
from django.test import TestCase
from django.utils import timezone


from tom_observations.facilities.lco import LCOImagingObservationForm
from tom_observations.tests.facilities.test_lco import generate_lco_proposal_choices
from tom_observations.tests.facilities.test_ocs import instrument_response
from tom_observations.tests.factories import SiderealTargetFactory


class TestLCOForm(TestCase):
    def setUp(self):
        self.enterContext(patch(
            'tom_observations.facilities.ocs.OCSBaseForm._get_instruments',
            return_value=instrument_response,
        ))
        self.enterContext(patch(
            'tom_observations.facilities.ocs.OCSBaseForm.proposal_choices',
            return_value=generate_lco_proposal_choices(),
        ))

        target = SiderealTargetFactory.create(ra=120.0, dec=30.0, pm_ra=0.0, pm_dec=0.0, epoch=2000)
        start = timezone.now() + timedelta(days=1)
        self.form = LCOImagingObservationForm({
            'name': 'test',
            'facility': 'LCO',
            'target_id': target.id,
            'proposal': 'sampleproposal',
            'ipp_value': 0.5,
            'observation_mode': 'NORMAL',
            'optimization_type': 'TIME',
            'start': start.isoformat(),
            'end': (start + timedelta(days=1)).isoformat(),
            'c_1_instrument_type': '1M0-SCICAM-SINISTRO',
            'c_1_configuration_type': 'EXPOSE',
            'c_1_guide_mode': 'ON',
            'c_1_max_airmass': 3.0,
            'c_1_min_lunar_distance': 20,
            'c_1_ic_1_exposure_count': 1,
            'c_1_ic_1_exposure_time': 30.0,
            'c_1_ic_1_filter': 'gp',
            'c_1_ic_1_readout_mode': 'full_frame',
        })

    def test_can_instantiate(self):
        form = LCOImagingObservationForm()

        self.assertIsInstance(form, PydanticValidationMixin)
        self.assertFalse(form.is_bound)

    @patch('tom_observations.facilities.lco.AeonLcoFacility.validate_request_group')
    def test_invalid_filter_is_rejected_by_aeonlib(self, mock_validate):
        """Test that an invalid filter choice is rejected by aeonlib before ever making
        a request to the LCO validation API."""
        field_name = 'c_1_ic_1_filter'
        field = self.form.fields[field_name]
        field.choices = [*field.choices, ('OIII', 'OIII')]
        self.form.data[field_name] = 'OIII'

        self.assertFalse(self.form.is_valid())
        self.assertEqual(self.form.errors.as_data()[field_name][0].code, 'literal_error')
        mock_validate.assert_not_called()

    @patch('tom_observations.facilities.lco.AeonLcoFacility.validate_request_group')
    def test_full_validation_with_aeonlib(self, mock_validate):
        """Test form validation using aeonlib's facility validation contract."""
        mock_validate.return_value = ValidationResult(valid=True, errors={}, duration=60)
        self.assertTrue(self.form.is_valid(), self.form.errors.as_json())
        mock_validate.assert_called_once()
        request_group = mock_validate.call_args.args[0]
        self.assertIsInstance(request_group, RequestGroup)
        self.assertEqual(request_group.name, 'test')
        self.assertEqual(request_group.requests[0].configurations[0].instrument_type, '1M0-SCICAM-SINISTRO')
        self.assertEqual(self.form.validation_message, 'This observation is valid with a duration of 60.0 seconds.')
