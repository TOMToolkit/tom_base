from astroplan import FixedTarget
from astroplan import moon_illumination as moon_illum
from astroplan import moon_phase_angle as moon_phase_angle
import astropy.units as u
from astropy.coordinates import AltAz, SkyCoord
from astropy.coordinates import get_moon as get_moon
import numpy as np
import warnings


def all_night_moon_sep(name, ra, dec, obs_night, obs_loc, sample_size=25):
    """
    Determines the min and max separations of the target object and the moon over a full
    observing night at the desired observatory. If it registers <15 degree separation at
    minimum, it prints a warning that the target object is too close to the moon.
    If it registers a <15 degree separation at maximum, the observation request is rejected.
    """
    try:
        coords = SkyCoord(ra*u.deg, dec*u.deg, frame='icrs')

        try:
            target = FixedTarget.from_name(name)
        except Exception:
            target = FixedTarget(name=name, coord=coords)

        obs_begin = obs_loc.twilight_evening_astronomical(obs_night, which='nearest')
        obs_end = obs_loc.twilight_morning_astronomical(obs_night, which='next')
        midnight = obs_loc.midnight(obs_night, which='nearest')
        lower_lim = (obs_begin - midnight).to(u.h)
        upper_lim = (obs_end - midnight).to(u.h)

        delta_midnight = np.linspace(lower_lim.value, upper_lim.value, sample_size)*u.hour
        frame_observing_night = AltAz(obstime=midnight+delta_midnight, location=obs_loc.location)
        targetaltaz_obsnight = coords.transform_to(frame_observing_night)
        moonaltaz_obsnight = get_moon(
            time=midnight+delta_midnight,
            location=obs_loc.location).transform_to(frame_observing_night)

        moon_frac = moon_illum(time=midnight+delta_midnight) * 100
        avg_moonill = np.mean(moon_frac)
        mphase = moon_phase_angle(time=midnight+delta_midnight).to(u.deg)
        avg_mphase = np.mean(mphase)
        # does not go to negatives: simply moves between 0 and 180 degrees, 0 being full moon and 180 being new moon

        sep_array = [y.separation(x) for x, y in zip(targetaltaz_obsnight, moonaltaz_obsnight)]
        sep_array_deg = [x.degree for x in sep_array]
        avg_sep = np.mean(sep_array_deg)

        if max(sep_array_deg) < 15:
            raise Exception('Object is too close to the moon on this date.')
        if min(sep_array_deg) <= 15 and max(sep_array_deg) >= 15:
            warnings.warn('Warning: Object is very close to the moon on this date.')
            print('Average separation is {0:.1f} degrees'.format(avg_sep))
        if min(sep_array_deg) >= 15:
            print('Average moon separation is {0:.1f} degrees'.format(avg_sep))
            print('{0:.1f} percent of the moon is illuminated'.format(avg_moonill))
            print('The average moon phase angle is {0:.1f}'.format(avg_mphase))
        else:
            print('Something really weird just happened')
    except (ValueError, AttributeError):
        print('Your dates were not inputted correctly.')
