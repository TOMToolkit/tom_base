from io import StringIO
from datetime import datetime, timedelta
from unittest import mock
from unittest.mock import patch

from django.test import TestCase
from django.urls import reverse
from django.conf import settings

import ephem
from rise_set.angle import Angle
from rise_set.astrometry import calc_sunrise_set

from .factories import TargetFactory, ObservingRecordFactory
from tom_targets.models import Target
from tom_observations.models import ObservationRecord
from tom_observations.facilities.lco import LCOFacility
from tom_observations.utils import get_rise_set, get_last_rise_set_pair, get_next_rise_set_pair


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
        self.rise_set = [(0, 10),
                         (20, 30),
                         (40, 50),
                         (60, 70)]
        self.observer = ephem.city('Los Angeles')
        self.sun = ephem.Sun()

    def test_get_rise_set_valid(self):
        rise_set = get_rise_set(self.observer, self.sun, datetime(2018, 10, 10), datetime(2018, 10, 11))
        self.assertListEqual([(datetime(2018, 10, 9, 13, 53, 16), datetime(2018, 10, 10, 1, 26, 33)),                               (datetime(2018, 10, 10, 13, 54, 2), datetime(2018, 10, 11, 1, 25, 15))],                               rise_set)

    def test_get_rise_set_against_lco_rise_set(self):
        lco = LCOFacility()
        sites = lco.get_observing_sites()
        start = datetime(2018, 10, 10)
        end = datetime(2018, 10, 11)

        # Get sunrise/set from rise-set library
        coj = {
            'latitude': Angle(degrees=sites.get('Siding Spring')['latitude']),
            'longitude': Angle(degrees=sites.get('Siding Spring')['longitude'])
        }
        coj_observer = lco.get_observer_for_site('Siding Spring')
        (transit, control_rise, control_set) = calc_sunrise_set(coj, start, 'sunrise')

        # Get rise/set from observations module
        rise_set = get_rise_set(coj_observer, self.sun, start, end)
        rise_delta = timedelta(hours=rise_set[0][0].hour, minutes=rise_set[0][0].minute, seconds=rise_set[0][0].second)
        set_delta = timedelta(hours=rise_set[0][1].hour, minutes=rise_set[0][1].minute, seconds=rise_set[0][1].second)
        self.assertLessEqual(rise_delta - control_rise, abs(timedelta(minutes=5)))
        self.assertLessEqual(set_delta - control_set, abs(timedelta(minutes=5)))

    def test_get_rise_set_no_results(self):
        rise_set = get_rise_set(self.observer, self.sun, datetime(2018, 10, 10, 7, 0, 0), datetime(2018, 10, 10, 7, 0, 1))
        self.assertEqual(len(rise_set), 0)

    def test_get_rise_set_invalid_params(self):
        self.assertRaisesRegex(Exception, 'Start must be before end', get_rise_set, self.observer, self.sun, datetime(2018, 10, 10), datetime(2018, 10, 9))

    def test_get_last_rise_set_pair(self):
        rise_set_pair = get_last_rise_set_pair(self.rise_set, -1)
        self.assertIsNone(rise_set_pair, None)
        rise_set_pair = get_last_rise_set_pair(self.rise_set, 25)
        self.assertEqual(rise_set_pair[0], 20)
        self.assertEqual(rise_set_pair[1], 30)
        rise_set_pair = get_last_rise_set_pair(self.rise_set, 80)
        self.assertEqual(rise_set_pair[0], 60)
        self.assertEqual(rise_set_pair[1], 70)

    def test_get_next_rise_set_pair(self):
        rise_set_pair = get_next_rise_set_pair(self.rise_set, -1)
        self.assertEqual(rise_set_pair[0], 0)
        self.assertEqual(rise_set_pair[1], 10)
        rise_set_pair = get_next_rise_set_pair(self.rise_set, 35)
        self.assertEqual(rise_set_pair[0], 40)
        self.assertEqual(rise_set_pair[1], 50)
        rise_set_pair = get_next_rise_set_pair(self.rise_set, 80)
        self.assertIsNone(rise_set_pair, None)
