from datetime import datetime, timedelta

import ephem
from bisect import bisect_left

EPHEM_FORMAT = '%Y/%m/%d %H:%M:%S'

def ephem_to_timestamp(ephem_time):
    """
    Converts PyEphem time object to a UNIX timestamp

    Parameters
    ----------
    ephem_time : PyEphem date
        time to be converted to UNIX

    Returns
    -------
    float
        UNIX time equivalent to the ephem_time

    """
    return datetime.strptime(str(ephem.date(ephem_time)), EPHEM_FORMAT).timestamp()


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
        both in UNIX time

    """
    if end_time < start_time:
        raise Exception('Start must be before end')
    observer.date = start_time
    start_time = start_time.timestamp()
    rise_set = []
    previous_setting = ephem_to_timestamp(observer.previous_setting(target))
    previous_rising = ephem_to_timestamp(observer.previous_rising(target))
    if previous_rising > previous_setting:
        next_setting = ephem_to_timestamp(observer.next_setting(target))
        rise_set.append((previous_rising, next_setting))
        start_time = next_setting + 1
    while start_time < end_time.timestamp():
        observer.date = datetime.fromtimestamp(start_time)
        next_rising = ephem_to_timestamp(observer.next_rising(target))
        next_setting = ephem_to_timestamp(observer.next_setting(target))
        if next_rising > start_time and next_rising < end_time.timestamp():
            rise_set.append((next_rising, next_setting))
        start_time = next_setting + 1
    return rise_set

def get_last_rise(rise_sets, time):
    """
    Gets the most recent rise before the given time, using a binary search

    Parameters
    ----------
    rise_sets : array
        array of tuples representing set of rise/sets to search
    time : float
        time value used to find the most recent rise, in UNIX time

    Returns
    -------
    float
        Most recent rise with respect to the given time

    """
    last_rise_pos = bisect_left(rise_sets, (time,))
    if last_rise_pos-1 < 0:
        return None
    return rise_sets[last_rise_pos-1][0]

def get_last_set(rise_sets, time):
    """
    Gets the most recent set before the given time, using a binary search

    Parameters
    ----------
    rise_sets : array
        array of tuples representing set of rise/sets to search
    time : float
        time value used to find the most recent set, in UNIX time

    Returns
    -------
    float
        Most recent set with respect to the given time

    """
    keys = [rise_set[1] for rise_set in rise_sets]
    last_set_pos = bisect_left(keys, time)
    if last_set_pos-1 < 0:
        return None
    return rise_sets[last_set_pos-1][1]

def get_next_rise(rise_sets, time):
    """
    Gets the upcoming rise after the given time, using a binary search

    Parameters
    ----------
    rise_sets : array
        array of tuples representing set of rise/sets to search
    time : float
        time value used to find the next rise, in UNIX time

    Returns
    -------
    float
        Soonest upcoming rise with respect to the given time

    """
    next_rise_pos = bisect_left(rise_sets, (time,))
    if next_rise_pos >= len(rise_sets):
        return None
    return rise_sets[next_rise_pos][0]

def get_next_set(rise_sets, time):
    """
    Gets the upcoming set after the given time, using a binary search

    Parameters
    ----------
    rise_sets : array
        array of tuples representing set of rise/sets to search
    time : float
        time value used to find the next set, in UNIX time

    Returns
    -------
    float
        Soonest upcoming set with respect to the given time

    """
    keys = [rise_set[1] for rise_set in rise_sets]
    next_set_pos = bisect_left(keys, time)
    if next_set_pos >= len(rise_sets):
        return None
    return rise_sets[next_set_pos][1]