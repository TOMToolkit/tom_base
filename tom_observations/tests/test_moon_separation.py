from astroplan import FixedTarget
from astroplan import moon_illumination as moon_illum
from astroplan import moon_phase_angle as moon_phase_angle
import astropy.units as u
from astropy.time import Time
from astropy.coordinates import SkyCoord, AltAz
from astropy.coordinates import get_moon as get_moon
from unittest.mock import patch
import numpy as np

from django.test import TestCase

from tom_observations.LCO_obs_locs import OGG
from tom_observations.moon_separation import all_night_moon_sep

test_target = ['M31', 10.6847083*u.deg, 41.2687500*u.deg]
date = Time("2021-05-04 00:00:00", scale='utc')
coords = SkyCoord(test_target[1], test_target[2], frame='icrs')
target = FixedTarget(name='M31', coord=coords)
obs_begin = OGG.twilight_evening_astronomical(date, which='nearest')
obs_end = OGG.twilight_morning_astronomical(date, which='next')
midnight = OGG.midnight(date, which='nearest')
lower_lim = (obs_begin - midnight).to(u.h)
upper_lim = (obs_end - midnight).to(u.h)

delta_midnight = np.linspace(lower_lim.value, upper_lim.value, 25)*u.hour
frame_observing_night = AltAz(obstime=midnight+delta_midnight, location=OGG.location)
targetaltaz_obsnight = coords.transform_to(frame_observing_night)
moonaltaz_obsnight = get_moon(time=midnight+delta_midnight,
                                location=OGG.location).transform_to(frame_observing_night)

moon_frac = moon_illum(time=midnight+delta_midnight) * 100
avg_moonill = np.mean(moon_frac)
mphase = moon_phase_angle(time=midnight+delta_midnight).to(u.deg)
avg_mphase = np.mean(mphase)

sep_array = [y.separation(x) for x, y in zip(targetaltaz_obsnight, moonaltaz_obsnight)]
sep_array_deg = [x.degree for x in sep_array]
avg_sep = np.mean(sep_array_deg)


class MoonSepCalc(TestCase):

    def test_coords(self):
        self.assertEqual(coords.ra, test_target[1])
        self.assertEqual(coords.dec, test_target[2])

    def test_target(self):
        self.assertEqual(target.name, test_target[0])

    def test_dates(self):
        t_obs_begin = obs_begin.to_value(format='iso')
        t_obs_end = obs_end.to_value(format='iso')
        t_midnight = midnight.to_value(format='iso')
        self.assertEqual(t_obs_begin, '2021-05-04 06:09:24.258')
        self.assertEqual(t_obs_end, '2021-05-04 14:33:56.825')
        self.assertEqual(t_midnight, '2021-05-04 10:21:40.084')

    def test_good_sep(self):
        f_avg_sep = round(avg_sep, 1)
        f_avg_moonill = round(avg_moonill, 1)
        f_avg_mphase = round(avg_mphase.value, 1)

        with self.subTest('Test the average separation.'):
            self.assertEqual(f_avg_sep, 73.4)

        with self.subTest('Test the average moon illumination.'):
            self.assertEqual(f_avg_moonill, 43.8)

        with self.subTest('Test the average moon phase angle.'):
            self.assertEqual(f_avg_mphase, 97.2)

    def test_too_close(self):
        with self.subTest('Test that an object too close to the moon returns an exception.'):
            with patch('tom_observations.moon_separation.all_night_moon_sep') as mock_all_night_moon_sep:
                mock_all_night_moon_sep.side_effect = Exception()
                with self.assertRaisesRegex(Exception, 'Object is too close to the moon on this date.'):
                    all_night_moon_sep('HD 205033', 323.2651667, -19.8063111,
                                        Time("2021-05-04 00:00:00", scale='utc'), OGG)
