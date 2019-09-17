from datetime import datetime, timedelta
from bisect import bisect_left
from astropy.coordinates import Angle, AltAz, get_sun, SkyCoord
from astropy import units
from astropy.time import Time
import ephem
from astroplan import Observer, FixedTarget, time_grid_from_range
import numpy as np

from tom_observations import facility

EPHEM_FORMAT = '%Y/%m/%d %H:%M:%S'

DEFAULT_VALUES = {
    'epoch': '2000'
}


def get_visibility(target, start_time, end_time, interval, airmass_limit=10):
    """
    Calculates the airmass for a target for each given interval between
    the start and end times.

    The resulting data omits any airmass above the provided limit (or
    default, if one is not provided), as well as any airmass calculated
    during the day.

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
    if not airmass_limit:
        airmass_limit = 10
    if target.type == target.SIDEREAL:
        visibility = get_sidereal_visibility(target, start_time, 
            end_time, interval, airmass_limit)
    elif target.type == target.NON_SIDEREAL:
        visibility = get_nonsidereal_visibility(target, start_time,
            end_time, interval, airmass_limit)
    else:
        raise Exception("Object type is unsupported for visibility calculations")

    return visibility



def get_nonsidereal_visibility(target, start_time, end_time, interval, airmass_limit):
    """
    Uses pyephem to calculate the airmass for a non-sidereal target 
    for each given interval between the start and end times.

    The resulting data omits any airmass above the provided limit (or
    default, if one is not provided), as well as any airmass calculated
    during the day.

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
    visibility = {}
    body = get_pyephem_instance_for_type(target)
    sun = ephem.Sun()
    for observing_facility in facility.get_service_classes():
        observing_facility_class = facility.get_service_class(observing_facility)
        sites = observing_facility_class().get_observing_sites()
        for site, site_details in sites.items():
            positions = [[], []]
            observer = get_pyephem_observer_for_site(site_details)
            rise_sets = get_rise_set(observer, sun, start_time, end_time)
            curr_interval = start_time
            while curr_interval <= end_time:
                time = curr_interval
                last_rise_set = get_last_rise_set_pair(rise_sets, time)
                sunup = time > last_rise_set[0] and time < last_rise_set[1] if last_rise_set else False
                observer.date = curr_interval
                body.compute(observer)
                alt = Angle(str(body.alt), unit=units.degree)
                az = Angle(str(body.az), unit=units.degree)
                altaz = AltAz(alt=alt.to_string(unit=units.rad), az=az.to_string(unit=units.rad))
                airmass = altaz.secz
                positions[0].append(curr_interval)
                positions[1].append(
                    airmass.value if (airmass.value > 1 and airmass.value <= airmass_limit) and not sunup else None
                )
                curr_interval += timedelta(minutes=interval)
            visibility['({0}) {1}'.format(observing_facility, site)] = positions
    return visibility


def ephem_to_datetime(ephem_time):
    """
    Converts PyEphem time object to a datetime object

    :param ephem_time: time to be converted to datetime
    :type ephem_time: PyEphem date

    :returns: datetime time equivalent to the ephem_time
    :rtype: datetime
    """
    return datetime.strptime(str(ephem_time), EPHEM_FORMAT)


def get_rise_set(observer, target, start_time, end_time):
    """
    Calculates all of the rises and sets for a target, from a position on Earth,
    within a given window.

    If the target is up at the start time, the rise is included in the result
    despite not being within the window. Similarly, if the target is up at the
    end time, the next setting beyond the end window is included in the result.

    :param observer: Represents the position from which to calculate the rise/sets
    :type observer: PyEphem Observer

    :param target: The object for which to calculate the rise/sets
    :type target: Target

    :param start_time: start of the calculation window
    :type start_time: datetime

    :param end_time: end of the calculation window
    :type end_time: datetime

    :returns: A list of 2-tuples, each a pair of values representing a rise and a set, both datetime objects
    :rtype: list
    """
    if end_time < start_time:
        raise Exception('Start must be before end')
    observer.date = start_time
    start_time = start_time
    rise_set = []
    previous_setting = ephem_to_datetime(observer.previous_setting(target))
    previous_rising = ephem_to_datetime(observer.previous_rising(target))
    if previous_rising > previous_setting:
        next_setting = ephem_to_datetime(observer.next_setting(target))
        rise_set.append((previous_rising, next_setting))
        start_time = next_setting + timedelta(seconds=1)
    while start_time < end_time:
        observer.date = start_time
        next_rising = ephem_to_datetime(observer.next_rising(target))
        next_setting = ephem_to_datetime(observer.next_setting(target))
        if next_rising > start_time and next_rising < end_time:
            rise_set.append((next_rising, next_setting))
        start_time = next_setting + timedelta(seconds=1)
    return rise_set


def get_last_rise_set_pair(rise_sets, time):
    """
    Gets the rise/set pair for the last rise before the given time, using a
    binary search

    :param rise_sets: array of tuples representing set of rise/sets to search
    :type rise_sets: array

    :param time: time value used to find the most recent rise, in UNIX time
    :type time: float

    :returns: Most recent rise/set pair with respect to the given time
    :rtype: tuple
    """
    last_rise_pos = bisect_left(rise_sets, (time,))
    if last_rise_pos <= 0:
        return None
    return rise_sets[last_rise_pos-1]


def get_next_rise_set_pair(rise_sets, time):
    """
    Gets the upcoming rise/set pair for the next rise after the given time,
    using a binary search

    :param rise_sets: array of tuples representing set of rise/sets to search
    :type rise_sets: array

    :param time: time value used to find the next rise, in UNIX time
    :type time: float

    :returns: Soonest upcoming rise/set with respect to the given time
    :rtype: tuple
    """
    next_rise_pos = bisect_left(rise_sets, (time,))
    if next_rise_pos >= len(rise_sets):
        return None
    return rise_sets[next_rise_pos]


def get_pyephem_instance_for_type(target):
    """
    Constructs a pyephem body for non-sidereal targets
    in order to perform positional calculations for the target

    :returns: EllipticalBody
    """
    body = ephem.EllipticalBody()
    body._inc = ephem.degrees(target.inclination) if target.inclination else 0
    body._Om = target.lng_asc_node if target.lng_asc_node else 0
    body._om = target.arg_of_perihelion if target.arg_of_perihelion else 0
    body._a = target.semimajor_axis if target.semimajor_axis else 0
    body._M = target.mean_anomaly if target.mean_anomaly else 0
    if target.ephemeris_epoch:
        epoch_M = Time(target.ephemeris_epoch, format='jd')
        epoch_M.format = 'datetime'
        body._epoch_M = ephem.Date(epoch_M.value)
    else:
        body._epoch_M = ephem.Date(DEFAULT_VALUES['epoch'])
    body._epoch = target.epoch if target.epoch else ephem.Date(DEFAULT_VALUES['epoch'])
    body._e = target.eccentricity if target.eccentricity else 0
    return body


def get_pyephem_observer_for_site(site):
    """
    Constructs a pyephem observer for non-sidereal targets
    in order to perform positional calculations for the target

    :returns: Observer
    """
    observer = ephem.Observer()
    observer.lon = ephem.degrees(str(site.get('longitude')))
    observer.lat = ephem.degrees(str(site.get('latitude')))
    observer.elevation = site.get('elevation')
    return observer



def get_sidereal_visibility(target, start_time, end_time, interval, airmass_limit):
    """
    Uses astroplan to calculate the airmass for a sidereal target 
    for each given interval between the start and end times.

    The resulting data omits any airmass above the provided limit (or
    default, if one is not provided), as well as any airmass calculated
    during the day (defined as between astronomical twilights).

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

    :returns: Observer
    """
    observer = Observer(
        longitude = site_details.get('longitude')*units.deg,
        latitude = site_details.get('latitude')*units.deg,
        elevation = site_details.get('elevation')*units.m
    )
    return observer
