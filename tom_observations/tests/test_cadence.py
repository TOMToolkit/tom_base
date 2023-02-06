from django.test import TestCase
from unittest.mock import patch
from datetime import datetime, timedelta
from dateutil.parser import parse

from .factories import ObservingRecordFactory, SiderealTargetFactory
from tom_observations.models import ObservationGroup, DynamicCadence
from tom_observations.cadences.resume_cadence_after_failure import ResumeCadenceAfterFailureStrategy
from tom_observations.cadences.retry_failed_observations import RetryFailedObservationsStrategy


mock_instruments = {
    '1M0-SCICAM-SINISTRO': {
        'type': 'IMAGE',
        'class': '1m0',
        'name': '1.0 meter Sinistro',
        'optical_elements': {
            'filters': [{'name': 'Bessell-I', 'code': 'I', 'schedulable': True, 'default': True}]
        },
        'default_configuration_type': 'EXPOSE'
    }
}

obs_params = {
    'facility': 'LCO',
    'observation_type': 'IMAGING',
    'name': 'With Perms',
    'ipp_value': 1.05,
    'start': '2020-01-01T00:00:00',
    'end': '2020-01-02T00:00:00',
    'exposure_count': 1,
    'exposure_time': 2.0,
    'max_airmass': 4.0,
    'observation_mode': 'NORMAL',
    'proposal': 'LCOSchedulerTest',
    'filter': 'I',
    'instrument_type': '1M0-SCICAM-SINISTRO'
}


@patch('tom_observations.facilities.ocs.OCSBaseForm._get_instruments', return_value=mock_instruments)
@patch('tom_observations.facilities.ocs.OCSBaseForm.proposal_choices',
       return_value=[('LCOSchedulerTest', 'LCOSchedulerTest')])
@patch('tom_observations.facilities.lco.LCOFacility.submit_observation', return_value=[198132])
@patch('tom_observations.facilities.lco.LCOFacility.validate_observation')
class TestReactiveCadencing(TestCase):
    def setUp(self):
        target = SiderealTargetFactory.create()
        obs_params['target_id'] = target.id
        obs_params['start'] = (datetime.now() - timedelta(hours=12)).strftime('%Y-%m-%dT%H:%M:%S')
        obs_params['end'] = (datetime.now() + timedelta(hours=12)).strftime('%Y-%m-%dT%H:%M:%S')
        observing_records = ObservingRecordFactory.create_batch(5,
                                                                target_id=target.id,
                                                                parameters=obs_params)
        self.group = ObservationGroup.objects.create()
        self.group.observation_records.add(*observing_records)
        self.group.save()
        self.dynamic_cadence = DynamicCadence.objects.create(
            cadence_strategy='Test Strategy', cadence_parameters={'cadence_frequency': 72}, active=True,
            observation_group=self.group)

    def test_retry_when_failed_cadence(self, patch1, patch2, patch3, patch4):
        num_records = self.group.observation_records.count()
        observing_record = self.group.observation_records.first()
        observing_record.status = 'CANCELED'
        observing_record.save()

        strategy = RetryFailedObservationsStrategy(self.dynamic_cadence)
        new_records = strategy.run()
        self.group.refresh_from_db()
        # Make sure the candence run created a new observation.
        self.assertEqual(num_records + 1, self.group.observation_records.count())
        # assert that the newly added observation record has a window of exactly 3 days
        # later than the canceled observation.
        self.assertEqual(
            parse(observing_record.parameters['start']),
            parse(new_records[0].parameters['start']) - timedelta(days=3)
        )

    @patch('tom_observations.facilities.lco.LCOFacility.get_observation_status', return_value={'state': 'CANCELED',
           'scheduled_start': None, 'scheduled_end': None})
    def test_resume_when_failed_cadence_failed_obs(self, mock_get_obs_status, mock_validate_obs, mock_submit_obs,
                                                   mock_proposal_choices, mock_get_insts):
        mock_validate_obs.return_value = {}
        num_records = self.group.observation_records.count()

        strategy = ResumeCadenceAfterFailureStrategy(self.dynamic_cadence)
        new_records = strategy.run()
        self.group.refresh_from_db()
        self.assertEqual(num_records + 1, self.group.observation_records.count())
        self.assertEqual(
            datetime.now().replace(second=0, microsecond=0),
            parse(new_records[0].parameters['start']).replace(second=0, microsecond=0)
        )

    @patch('tom_observations.facilities.lco.LCOFacility.get_observation_status', return_value={'state': 'COMPLETED',
           'scheduled_start': None, 'scheduled_end': None})
    def test_resume_when_failed_cadence_successful_obs(self, mock_get_obs_status, mock_validate_obs, mock_submit_obs,
                                                       mock_proposal_choices, mock_get_insts):
        mock_validate_obs.return_value = {}
        num_records = self.group.observation_records.count()
        obsr = self.group.observation_records.order_by('-created').first()

        strategy = ResumeCadenceAfterFailureStrategy(self.dynamic_cadence)
        new_records = strategy.run()
        self.group.refresh_from_db()
        self.assertEqual(num_records + 1, self.group.observation_records.count())
        self.assertAlmostEqual(
            parse(obsr.parameters['start']).replace(second=0, microsecond=0),
            parse(new_records[0].parameters['start']).replace(second=0, microsecond=0) - timedelta(days=3)
        )

    @patch('tom_observations.facilities.lco.LCOFacility.get_observation_status', return_value={'state': 'COMPLETED',
           'scheduled_start': None, 'scheduled_end': None})
    def test_resume_when_failed_cadence_invalid_date(self, mock_get_obs_status, mock_validate_obs, mock_submit_obs,
                                                     mock_proposal_choices, mock_get_insts):
        mock_validate_obs.return_value = {}
        num_records = self.group.observation_records.count()
        obsr = self.group.observation_records.order_by('-created').first()
        obsr.parameters['start'] = (datetime.now() - timedelta(days=7)).strftime('%Y-%m-%dT%H:%M:%S')
        obsr.parameters['end'] = (datetime.now() - timedelta(days=6)).strftime('%Y-%m-%dT%H:%M:%S')
        obsr.save()

        strategy = ResumeCadenceAfterFailureStrategy(self.dynamic_cadence)
        new_records = strategy.run()
        self.group.refresh_from_db()
        self.assertEqual(num_records + 1, self.group.observation_records.count())
        self.assertAlmostEqual(
            datetime.now().replace(second=0, microsecond=0),
            parse(new_records[0].parameters['start']).replace(second=0, microsecond=0)
        )

    @patch('tom_observations.facilities.lco.LCOFacility.get_observation_status', return_value={'state': 'COMPLETED',
           'scheduled_start': None, 'scheduled_end': None})
    def test_resume_when_failed_cadence_obs_invalid(self, mock_get_obs_status, mock_validate_obs, mock_submit_obs,
                                                    mock_proposal_choices, mock_get_insts):
        mock_validate_obs.return_value = {'errors': {'end': 'Window end time must be in the future'}}

        strategy = ResumeCadenceAfterFailureStrategy(self.dynamic_cadence)
        with self.assertRaises(Exception):
            strategy.run()
