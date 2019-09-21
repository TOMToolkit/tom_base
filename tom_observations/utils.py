from astropy.coordinates import get_sun, SkyCoord
from astropy import units
from astropy.time import Time
from astroplan import Observer, FixedTarget, time_grid_from_range
import numpy as np
import logging

from tom_observations import facility

logger = logging.getLogger(__name__)

def get_visibility(target, start_time, end_time, interval, airmass_limit):
    """
    Uses astroplan to calculate the airmass for a sidereal target 
    for each given interval between the start and end times.

    The resulting data omits any airmass above the provided limit (or
    default, if one is not provided), as well as any airmass calculated
    during the day (defined as between astronomical twilights).

    Important note: only works for sidereal targets!

    :param start_time: start of the window for which to calculate the airmass
    :type start_time: datetime

    :param end_time: end of the window for which to calculate the airmass
    :type end_time: datetime

    :param interval: time interval, in minutes, at which to calculate airmass within the given window
    :type interval: int

    :param airmass_limit: maximum acceptable airmass for the resulting calculations
    :type airmass_limit: int

    :returns: A dictionary containing the airmass data for each site. The dict keys consist of the site name prepended
        with the observing facility. The values are the airmass data, structured as an array containing two arrays. The
        first array contains the set of datetimes used in the airmass calculations. The second array contains the
        corresponding set of airmasses calculated.
    :rtype: dict
    """

    if target.type != 'SIDEREAL':
        msg = '\033[1m\033[91mAirmass plotting is only supported for sidereal targets\033[0m'
        logger.info(msg)
        empty_visibility = {}
        return empty_visibility

    if airmass_limit is None:
        airmass_limit = 10

    visibility = {}
    body = get_astroplan_instance_for_type(target)
    sun, time_range = get_astroplan_sun_and_time(start_time, end_time, interval)
    for observing_facility in facility.get_service_classes():
        observing_facility_class = facility.get_service_class(observing_facility)
        sites = observing_facility_class().get_observing_sites()
        for site, site_details in sites.items():

            observer = get_astroplan_observer_for_site(site_details)

            sun_alt = observer.altaz(time_range, sun).alt
            obj_airmass = observer.altaz(time_range, body).secz

            bad_indices = np.argwhere(
                (obj_airmass >= airmass_limit) |
                (obj_airmass <= 1) |
                (sun_alt > -18*units.deg) #between astro twilights
            )

            obj_airmass = [None if i in bad_indices else float(x)
                for i, x in enumerate(obj_airmass)]

            visibility['({0}) {1}'.format(observing_facility, site)] = [time_range.datetime, obj_airmass]
    return visibility


def get_astroplan_instance_for_type(target):
    """
    Constructs an astroplan FixedTarget from a tom_targets target
    in order to perform positional calculations for the target.

    :param target: the target
    :type target: tom_targets.models.Target

    :returns: a fixed target at the target's ra and dec
    :rtype: astroplan FixedTarget
    """

    fixed_target = FixedTarget(name = target.name,
        coord = SkyCoord(
            target.ra,
            target.dec,
            unit = 'deg'
        )
    )

    return fixed_target
    

def get_astroplan_sun_and_time(start_time, end_time, interval):
    """
    Uses astroplan's time_grid_from_range to generate
    an astropy Time object covering the time range.

    Uses astropy's get_sun to generate sun positions over
    that time range.

    If time range is small and interval is coarse, approximates
    the sun at a fixed position from the middle of the
    time range to speed up calculations.
    Since the sun moves ~4 minutes a day, this approximation
    happens when the number of days covered by the time range
    * 4 is less than the interval (in minutes) / 2.

    :param start_time: start of the window for which to calculate the airmass
    :type start_time: datetime

    :param end_time: end of the window for which to calculate the airmass
    :type end_time: datetime

    :param interval: time interval, in minutes, at which to calculate airmass within the given window
    :type interval: int

    :returns: ra/dec positions of the sun over the time range,
        time range between start_time and end_time at interval
    :rtype: astropy SkyCoord, astropy Time
    """

    start = Time(start_time)
    end = Time(end_time)

    time_range = time_grid_from_range(
        time_range = [start, end],
        time_resolution = interval*units.minute
    )

    number_of_days = end.mjd - start.mjd
    if number_of_days*4 < float(interval)/2:
        #Hack to speed up calculation by factor of ~3
        sun_coords = get_sun(time_range[int(len(time_range)/2)])
        fixed_sun = FixedTarget(name = 'sun',
            coord = SkyCoord(
                sun_coords.ra,
                sun_coords.dec,
                unit = 'deg'
            )
        )
        sun = fixed_sun
    else:
        sun = get_sun(time_range)

    return sun, time_range


def get_astroplan_observer_for_site(site_details):
    """
    Constructs an astroplan observer for sidereal targets
    in order to perform positional calculations for the target

    :returns: astroplan Observer
    """
    observer = Observer(
        longitude = site_details.get('longitude')*units.deg,
        latitude = site_details.get('latitude')*units.deg,
        elevation = site_details.get('elevation')*units.m
    )
    return observer
