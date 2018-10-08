from datetime import datetime, timedelta

import ephem
from tom_observations.rise_set import RiseSetTree, RiseSetPair

ephem_format = '%Y/%m/%d %H:%M:%S'

def get_rise_set(observer, target, start_time, end_time):
    observer.date = start_time
    rise_set = RiseSetTree()
    previous_setting = datetime.strptime(str(ephem.date(observer.previous_setting(target))), ephem_format)
    previous_rising = datetime.strptime(str(ephem.date(observer.previous_rising(target))), ephem_format)
    if previous_rising > previous_setting:
        next_setting = datetime.strptime(str(ephem.date(observer.next_setting(target))), ephem_format)
        rise_set.add_rise_set_pair(RiseSetPair(previous_rising, next_setting))
        start_time = datetime.strptime(str(ephem.date(next_setting)), ephem_format) + timedelta(seconds=1)
    while start_time < end_time:
        observer.date = start_time
        next_rising = datetime.strptime(str(ephem.date(observer.next_rising(target))), ephem_format)
        next_setting = datetime.strptime(str(ephem.date(observer.next_setting(target))), ephem_format)
        rise_set.add_rise_set_pair(RiseSetPair(next_rising, next_setting))
        start_time = datetime.strptime(str(ephem.date(next_setting)), ephem_format) + timedelta(seconds=1)
    return rise_set