from astroplan import AltitudeConstraint, AirmassConstraint, AtNightConstraint
from astroplan import is_observable
from astroplan import FixedTarget
from astropy.coordinates import SkyCoord
from astropy.time import Time
import astropy.units as u


def timeobj(date):
    obs_night = Time(date, format='iso', scale='utc')
    return obs_night

def calculate_visibility(name, ra, dec, obs_night, obs_location, max_airmass=2.0):
    """
    Visibility calculator for a single target.  Constraints include airmass, altitude,
    AtNight, and moon separation, among others.
    """
    try:
        coords = SkyCoord(ra*u.deg, dec*u.deg, frame='icrs')
        try:
            target = FixedTarget.from_name(name)
        except Exception:
            target = FixedTarget(name=name, coord=coords)
        obs_begin = obs_location.twilight_evening_astronomical(obs_night, which='nearest')
        obs_end = obs_location.twilight_morning_astronomical(obs_night, which='next')
        observing_range = [obs_begin, obs_end]
        constraints = [AirmassConstraint(max_airmass), AltitudeConstraint(20*u.deg, 85*u.deg), AtNightConstraint.twilight_astronomical()]
        ever_observable = is_observable(constraints, obs_location, target, time_range=observing_range)
        if ever_observable:
            pass
        else:
            raise Exception('This object is not observable by MuSCAT on this date.')
    except ValueError:
        print('Your dates were not inputted correctly.')
