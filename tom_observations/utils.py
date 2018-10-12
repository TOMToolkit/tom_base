from datetime import datetime, timedelta

import ephem
from bisect import bisect_left

EPHEM_FORMAT = '%Y/%m/%d %H:%M:%S'

def ephem_to_timestamp(ephem_time):
    return datetime.strptime(str(ephem.date(ephem_time)), EPHEM_FORMAT).timestamp()

def get_rise_set(observer, target, start_time, end_time):
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
    last_rise_pos = bisect_left(rise_sets, (time,))
    if last_rise_pos-1 < 0:
        return None
    return rise_sets[last_rise_pos-1][0]

def get_last_set(rise_sets, time):
    keys = [rise_set[1] for rise_set in rise_sets]
    last_set_pos = bisect_left(keys, time)
    if last_set_pos-1 < 0:
        return None
    return rise_sets[last_set_pos-1][1]

def get_next_rise(rise_sets, time):
    next_rise_pos = bisect_left(rise_sets, (time,))
    if next_rise_pos >= len(rise_sets):
        return None
    return rise_sets[next_rise_pos][0]

def get_next_set(rise_sets, time):
    keys = [rise_set[1] for rise_set in rise_sets]
    next_set_pos = bisect_left(keys, time)
    if next_set_pos >= len(rise_sets):
        return None
    return rise_sets[next_set_pos][1]