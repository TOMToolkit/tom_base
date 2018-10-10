from io import StringIO
from datetime import datetime, timedelta
from unittest import mock
from unittest.mock import patch

from django.test import TestCase
from django.urls import reverse
from django.conf import settings

import ephem

from .factories import TargetFactory, ObservingRecordFactory
from tom_targets.models import Target
from tom_observations.models import ObservationRecord
from tom_observations.facilities.lco import LCOFacility
from tom_observations.utils import get_rise_set, get_last_rise, get_last_set, get_next_rise, get_next_set


class TestLCOFacility(TestCase):
    def setUp(self):
        self.t1 = TargetFactory.create()
        self.or1 = ObservingRecordFactory.create(target_id=self.t1.id, status='PENDING')
        self.or2 = ObservingRecordFactory.create(target_id=self.t1.id, status='COMPLETED')
        self.or3 = ObservingRecordFactory.create(target_id=self.t1.id, facility='Fake Facility', status='PENDING')
        self.t2 = TargetFactory.create()
        self.or4 = ObservingRecordFactory.create(target_id=self.t2.id, status='PENDING')

    # Tests that only 2 of the three created observing records are updated, as
    # the third is in a completed state
    def test_update_all_observations_for_facility(self):
        with mock.patch.object(LCOFacility, 'update_observation_status') as uos_mock:
            LCOFacility().update_all_observation_statuses()
            self.assertEquals(uos_mock.call_count, 2)

    # Tests that only the observing records associated with the given target are updated
    def test_update_individual_target_observations_for_facility(self):
        with mock.patch.object(LCOFacility, 'update_observation_status', return_value='COMPLETED') as uos_mock:
            LCOFacility().update_all_observation_statuses(target=self.t1)
            self.assertEquals(uos_mock.call_count, 1)

class TestRiseSet(TestCase):
    def setUp(self):
        # now = datetime.now()
        # self.rise_set = [
        #     (now, now+timedelta(minutes=10)),
        #     (now+timedelta(minutes=20), now+timedelta(minutes=30)),
        #     (now+timedelta(minutes=40), now+timedelta(minutes=50)),
        #     (now+timedelta(minutes=60), now+timedelta(minutes=70))
        # ]
        self.rise_set = [
            (0, 10),
            (20, 30),
            (40, 50),
            (60, 70)
        ]

    # @patch('tom_observations.utils.ephem')
    # def test_get_rise_set(self, MockEphem):
    #     observer = MockEphem.Observer()
    #     target = MockEphem.Mars()
    #     rise_set = get_rise_set(observer, target, datetime(2018, 10, 10), datetime(2018, 10, 11))
    #     print(rise_set)

    def test_get_last_rise(self):
        self.assertIsNone(get_last_rise(self.rise_set, -1), None)
        self.assertEqual(get_last_rise(self.rise_set, 35), 20)
        self.assertEqual(get_last_rise(self.rise_set, 80), 60)

    def test_get_last_set(self):
        self.assertIsNone(get_last_set(self.rise_set, -1), None)
        self.assertEqual(get_last_set(self.rise_set, 35), 30)
        self.assertEqual(get_last_set(self.rise_set, 80), 70)

    def test_get_next_rise(self):
        self.assertEqual(get_next_rise(self.rise_set, -1), 0)
        self.assertEqual(get_next_rise(self.rise_set, 35), 40)
        self.assertIsNone(get_next_rise(self.rise_set, 80), None)

    def test_get_next_set(self):
        self.assertEqual(get_next_set(self.rise_set, -1), 10)
        self.assertEqual(get_next_set(self.rise_set, 35), 50)
        self.assertIsNone(get_next_set(self.rise_set, 80), None)