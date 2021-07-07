import unittest
import sys
import json
from unittest.mock import patch
from unittest.mock import MagicMock
from django import forms

import numpy as np
import astropy.units as u
from astropy.time import Time
from astropy.coordinates import SkyCoord
import pytz

from django.test import TestCase, override_settings

from astroplan import Observer, FixedTarget
from astroplan import time_grid_from_range
from astroplan.plots import plot_airmass
from astroplan import AltitudeConstraint, AirmassConstraint, AtNightConstraint
from astroplan import observability_table
from astroplan import is_observable, is_always_observable, months_observable
from singletarget_vis import calculate_visibility

muscat_loc = Observer(
                    longitude = -156.2568 * u.deg,
                    latitude = 20.7082 * u.deg,
                    elevation = 3052 * u.m,
                    timezone = 'US/Hawaii',
                    name = "Haleakala Observatory"
                    )

test_target = ['Sirius', 100.7362500*u.deg, -16.6459444*u.deg]
date = Time("2019-12-25 00:00:00", scale='utc')
coords = SkyCoord(test_target[1], test_target[2], frame='icrs')
target = FixedTarget(name='Sirius', coord=coords)
obs_begin = muscat_loc.twilight_evening_astronomical(date, which='nearest')
obs_end = muscat_loc.twilight_morning_astronomical(date, which='next')
observing_range = [obs_begin, obs_end]
constraints = [AirmassConstraint(2.0), AltitudeConstraint(25*u.deg, 85*u.deg), AtNightConstraint.twilight_astronomical()]
ever_observable = is_observable(constraints, muscat_loc, target, time_range=observing_range)

class TestVisibilityCalc(TestCase):

    def test_timeobj(self):
        self.assertEqual(date.scale, 'utc')
        self.assertEqual(date.value, '2019-12-25 00:00:00.000')

    def test_coords(self):
        self.assertEqual(coords.ra, test_target[1])
        self.assertEqual(coords.dec, test_target[2])

    def test_target(self):
        self.assertEqual(target.name, test_target[0])

    def test_dates(self):
        t_obs_begin = obs_begin.to_value(format='iso')
        t_obs_end = obs_end.to_value(format='iso')
        self.assertEqual(t_obs_begin, '2019-12-25 05:10:04.800')
        self.assertEqual(t_obs_end, '2019-12-25 15:39:42.586')

    def test_ever_obs(self):
        self.assertEqual(ever_observable, True)

    def test_not_obs(self):
        with self.subTest('Test that an invalid object returns an exception.'):
            with patch('singletarget_vis.calculate_visibility') as mock_calculate_visibility:
                mock_calculate_visibility.side_effect = Exception('This object is not observable by MuSCAT on this date.')
                with self.assertRaises(Exception):
                    mock_calculate_visibility()

    def test_bad_dates(self):
        with self.subTest('Test that an invalid date returns a ValueError.'):
            with patch('singletarget_vis.calculate_visibility') as mock_calculate_visibility:
                mock_calculate_visibility.side_effect = ValueError('Your dates were not inputted correctly.')
                with self.assertRaises(ValueError):
                    mock_calculate_visibility()
