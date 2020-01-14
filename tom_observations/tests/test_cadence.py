from django.test import TestCase
from unittest.mock import patch
from datetime import timedelta
from dateutil.parser import parse

from .factories import ObservingRecordFactory, TargetFactory
from tom_observations.models import ObservationGroup
from tom_observations.cadence import RetryFailedObservationsStrategy


@patch('tom_observations.facilities.lco.LCOFacility.submit_observation', return_value=[198132])
@patch('tom_observations.facilities.lco.LCOFacility.validate_observation')
class TestReactiveCadencing(TestCase):
    def setUp(self):
        target = TargetFactory.create()
        observing_records = ObservingRecordFactory.create_batch(5, target_id=target.id)
        self.group = ObservationGroup.objects.create()
        self.group.observation_records.add(*observing_records)
        self.group.save()

    def test_retry_when_failed_cadence(self, patch1, patch2):
        num_records = self.group.observation_records.count()
        observing_record = self.group.observation_records.first()
        observing_record.status = 'CANCELED'
        observing_record.save()

        strategy = RetryFailedObservationsStrategy(self.group, advance_window_days=3)
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
