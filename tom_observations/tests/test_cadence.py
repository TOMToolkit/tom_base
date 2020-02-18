from django.test import TestCase
from unittest.mock import patch
from datetime import datetime, timedelta
from dateutil.parser import parse

from .factories import ObservingRecordFactory, TargetFactory
from tom_observations.models import ObservationGroup
from tom_observations.cadence import RetryFailedObservationsStrategy, ResumeCadenceAfterFailureStrategy


mock_filters = {'1M0-SCICAM-SINISTRO': {
                    'type': 'IMAGE',
                    'class': '1m0',
                    'name': '1.0 meter Sinistro',
                    'optical_elements': {
                        'filters': [{'name': 'Bessell-I', 'code': 'I'}]}
                    }
                }


@patch('tom_observations.facilities.lco.LCOBaseForm._get_instruments', return_value=mock_filters)
@patch('tom_observations.facilities.lco.LCOBaseForm.proposal_choices',
       return_value=[('LCOSchedulerTest', 'LCOSchedulerTest')])
@patch('tom_observations.facilities.lco.LCOFacility.submit_observation', return_value=[198132])
@patch('tom_observations.facilities.lco.LCOFacility.validate_observation')
class TestReactiveCadencing(TestCase):
    def setUp(self):
        target = TargetFactory.create()
        observing_records = ObservingRecordFactory.create_batch(5, target_id=target.id)
        self.group = ObservationGroup.objects.create()
        self.group.observation_records.add(*observing_records)
        self.group.save()

    def test_retry_when_failed_cadence(self, patch1, patch2, patch3, patch4):
        num_records = self.group.observation_records.count()
        observing_record = self.group.observation_records.first()
        observing_record.status = 'CANCELED'
        observing_record.save()

        strategy = RetryFailedObservationsStrategy(self.group, 72)
        new_records = strategy.run()
        self.group.refresh_from_db()
        # Make sure the candence run created a new observation.
        self.assertEqual(num_records + 1, self.group.observation_records.count())
        # assert that the newly added observation record has a window of exactly 3 days
        # later than the canceled observation.
        self.assertEqual(
            parse(observing_record.parameters_as_dict['start']),
            parse(new_records[0].parameters_as_dict['start']) - timedelta(days=3)
        )

    @patch('tom_observations.facilities.lco.LCOFacility.get_observation_status', return_value={'state': 'CANCELED',
           'scheduled_start': None, 'scheduled_end': None})
    def test_resume_when_failed_cadence_failed_obs(self, patch1, patch2, patch3, patch4, patch5):
        num_records = self.group.observation_records.count()

        strategy = ResumeCadenceAfterFailureStrategy(self.group, 72)
        new_records = strategy.run()
        self.group.refresh_from_db()
        self.assertEqual(num_records + 1, self.group.observation_records.count())
        self.assertEqual(
            datetime.now().replace(second=0, microsecond=0),
            parse(new_records[0].parameters_as_dict['start']).replace(second=0, microsecond=0)
        )

    @patch('tom_observations.facilities.lco.LCOFacility.get_observation_status', return_value={'state': 'COMPLETED',
           'scheduled_start': None, 'scheduled_end': None})
    def test_resume_when_failed_cadence_successful_obs(self, patch1, patch2, patch3, patch4, patch5):
        num_records = self.group.observation_records.count()
        observing_record = self.group.observation_records.order_by('-created').first()

        strategy = ResumeCadenceAfterFailureStrategy(self.group, 72)
        new_records = strategy.run()
        self.group.refresh_from_db()
        self.assertEqual(num_records + 1, self.group.observation_records.count())
        self.assertAlmostEqual(
            parse(observing_record.parameters_as_dict['start']),
            parse(new_records[0].parameters_as_dict['start']) - timedelta(days=3)
        )
