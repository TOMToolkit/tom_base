from astroplan import AltitudeConstraint, AirmassConstraint, AtNightConstraint
from astroplan import is_observable, FixedTarget
from astropy.coordinates import SkyCoord
from astropy.time import Time
import astropy.units as u
from unittest.mock import patch

from django.test import TestCase

from tom_observations.LCO_obs_locs import OGG
from singletarget_vis import calculate_visibility

test_target = ['Sirius', 100.7362500*u.deg, -16.6459444*u.deg]
date = Time("2019-12-25 00:00:00", scale='utc')
coords = SkyCoord(test_target[1], test_target[2], frame='icrs')
target = FixedTarget(name='Sirius', coord=coords)
obs_begin = OGG.twilight_evening_astronomical(date, which='nearest')
obs_end = OGG.twilight_morning_astronomical(date, which='next')
observing_range = [obs_begin, obs_end]
constraints = [AirmassConstraint(2.0), AltitudeConstraint(20*u.deg, 85*u.deg),
                AtNightConstraint.twilight_astronomical()]
ever_observable = is_observable(constraints, OGG, target, time_range=observing_range)


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
        self.assertEqual(t_obs_begin, '2019-12-25 05:10:04.696')
        self.assertEqual(t_obs_end, '2019-12-25 15:39:42.359')

    def test_ever_obs(self):
        self.assertTrue(ever_observable)

    def test_not_obs(self):
        with self.subTest('Test that an invalid object returns an exception.'):
            with patch('tom_observations.singletarget_vis.calculate_visibility') as mock_calculate_visibility:
                mock_calculate_visibility.side_effect = Exception()
                with self.assertRaisesRegex(Exception, 'This object is not observable by MuSCAT on this date.'):
                    calculate_visibility('Polaris', 37.954, 89.264, Time("2019-12-25 00:00:00", scale='utc'), OGG)
