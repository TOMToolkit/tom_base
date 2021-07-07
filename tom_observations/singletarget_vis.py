import numpy as np
import astropy.units as u
from astropy.time import Time
from astropy.coordinates import SkyCoord
import pytz

from astroplan import Observer, FixedTarget
from astroplan import time_grid_from_range
from astroplan.plots import plot_airmass
from astroplan import AltitudeConstraint, AirmassConstraint, AtNightConstraint
from astroplan import observability_table
from astroplan import is_observable, is_always_observable, months_observable

"""
Visibility calculator for a single target.  Constraints include airmass, altitude,
AtNight, and moon separation, among others.
"""

muscat_loc = Observer(
                    longitude = -156.2568 * u.deg,
                    latitude = 20.7082 * u.deg,
                    elevation = 3052 * u.m,
                    timezone = 'US/Hawaii',
                    name = "Haleakala Observatory"
                    )
def timeobj(date):
    obs_night = Time(date, format='iso', scale='utc')
    return obs_night

def calculate_visibility(name, ra, dec, obs_night, max_airmass):
    try:
        coords = SkyCoord(ra*u.deg, dec*u.deg, frame='icrs')
        target = FixedTarget(name=name, coord=coords)
        obs_begin = muscat_loc.twilight_evening_astronomical(obs_night, which='nearest')
        obs_end = muscat_loc.twilight_morning_astronomical(obs_night, which='next')
        observing_range = [obs_begin, obs_end]
        constraints = [AirmassConstraint(max_airmass), AltitudeConstraint(25*u.deg, 85*u.deg), AtNightConstraint.twilight_astronomical()]
        ever_observable = is_observable(constraints, muscat_loc, target, time_range=observing_range)
        if ever_observable:
            pass
        else:
            raise Exception('This object is not observable by MuSCAT on this date.')
    except ValueError:
        print('Your dates were not inputted correctly.')
        #make an error for if observing_range is empty
        #"For accurate visibility information, please make sure your Time object is in UTC"
