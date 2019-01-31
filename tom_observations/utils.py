from datetime import datetime, timedelta
from bisect import bisect_left
from astropy.coordinates import Angle, AltAz
from astropy import units
from astropy.time import Time
import ephem

from tom_observations import facility

EPHEM_FORMAT = '%Y/%m/%d %H:%M:%S'

DEFAULT_VALUES = {
    'epoch': '2000'
}


def ephem_to_datetime(ephem_time):
    """
    Converts PyEphem time object to a datetime object

    Parameters
    ----------
    ephem_time : PyEphem date
        time to be converted to datetime

    Returns
    -------
    datetime
        datetime time equivalent to the ephem_time

    """
    return datetime.strptime(str(ephem_time), EPHEM_FORMAT)


def get_rise_set(observer, target, start_time, end_time):
    """
    Calculates all of the rises and sets for a target, from a position on Earth,
    within a given window.

    If the target is up at the start time, the rise is included in the result
    despite not being within the window. Similarly, if the target is up at the
    end time, the next setting beyond the end window is included in the result.

    Parameters
    ----------
    observer : PyEphem Observer
        Represents the position from which to calculate the rise/sets
    target : Target
        The object for which to calculate the rise/sets
    start_time : datetime
        start of the calculation window
    end_time : datetime
        end of the calculation window

    Returns
    -------
    array
        An array of tuples, each a pair of values representing a rise and a set,
        both datetime objects

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

    Parameters
    ----------
    rise_sets : array
        array of tuples representing set of rise/sets to search
    time : float
        time value used to find the most recent rise, in UNIX time

    Returns
    -------
    tuple
        Most recent rise/set pair with respect to the given time

    """
    last_rise_pos = bisect_left(rise_sets, (time,))
    if last_rise_pos <= 0:
        return None
    return rise_sets[last_rise_pos-1]


def get_next_rise_set_pair(rise_sets, time):
    """
    Gets the upcoming rise/set pair for the next rise after the given time,
    using a binary search

    Parameters
    ----------
    rise_sets : array
        array of tuples representing set of rise/sets to search
    time : float
        time value used to find the next rise, in UNIX time

    Returns
    -------
    tuple
        Soonest upcoming rise/set with respect to the given time

    """
    next_rise_pos = bisect_left(rise_sets, (time,))
    if next_rise_pos >= len(rise_sets):
        return None
    return rise_sets[next_rise_pos]


def get_visibility(target, start_time, end_time, interval, airmass_limit=10):
    """
    Calculates the airmass for a target for each given interval between
    the start and end times.

    The resulting data omits any airmass above the provided limit (or
    default, if one is not provided), as well as any airmass calculated
    during the day.

    Parameters
    ----------
    start_time : datetime
        start of the window for which to calculate the airmass
    end_time : datetime
        end of the window for which to calculate the airmass
    interval : int
        time interval, in minutes, at which to calculate airmass within
        the given window
    airmass_limit : int
        maximum acceptable airmass for the resulting calculations

    Returns
    -------
    dict
        A dictionary containing the airmass data for each site. The
        dict keys consist of the site name prepended with the observing
        facility. The values are the airmass data, structured as an
        array containing two arrays. The first array contains the set
        of datetimes used in the airmass calculations. The second array
        contains the corresponding set of airmasses calculated.

    """
    if not airmass_limit:
        airmass_limit = 10
    visibility = {}
    body = get_pyephem_instance_for_type(target)
    sun = ephem.Sun()
    for observing_facility in facility.get_service_classes():
        observing_facility_class = facility.get_service_class(observing_facility)
        sites = observing_facility_class().get_observing_sites()
        for site, site_details in sites.items():
            positions = [[], []]
            observer = observer_for_site(site_details)
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


def get_pyephem_instance_for_type(target):
    """
    Constructs a pyephem body corresponding to the proper object type
    in order to perform positional calculations for the target

    Returns
    -------
    FixedBody or EllipticalBody

    Raises
    ------
    Exception
        When a target type other than sidereal or non-sidereal is supplied

    """
    if target.type == target.SIDEREAL:
        body = ephem.FixedBody()
        body._ra = Angle(str(target.ra) + 'd').to_string(unit=units.hourangle, sep=':')
        body._dec = Angle(str(target.dec) + 'd').to_string(unit=units.degree, sep=':')
        body._epoch = target.epoch if target.epoch else ephem.Date(DEFAULT_VALUES['epoch'])
        return body
    elif target.type == target.NON_SIDEREAL:
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
    else:
        raise Exception("Object type is unsupported for visibility calculations")


def observer_for_site(site):
    observer = ephem.Observer()
    observer.lon = ephem.degrees(str(site.get('longitude')))
    observer.lat = ephem.degrees(str(site.get('latitude')))
    observer.elevation = site.get('elevation')
    return observer
