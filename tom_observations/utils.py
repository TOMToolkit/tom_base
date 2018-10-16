from datetime import datetime, timedelta

import ephem
from bisect import bisect_left

EPHEM_FORMAT = '%Y/%m/%d %H:%M:%S'

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
