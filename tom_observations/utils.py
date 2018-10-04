from datetime import datetime, timedelta

import ephem
from tom_observations.rise_set import RiseSetTree, RiseSetPair

ephem_format = '%Y/%m/%d %H:%M:%S'

# TODO: modify for loop to a while loop that shifts start time to the next_setting of previous iteration
def get_rise_set(observer, target, start_time, end_time):
    observer.date = start_time
    rise_set = RiseSetTree()
    previous_setting = datetime.strptime(str(ephem.date(observer.previous_setting(target))), ephem_format)
    previous_rising = datetime.strptime(str(ephem.date(observer.previous_rising(target))), ephem_format)
    if previous_rising > previous_setting:
        next_setting = datetime.strptime(str(ephem.date(observer.next_setting(target))), ephem_format)
        rise_set.add_rise_set_pair(RiseSetPair(previous_rising, next_setting))
        start_time = datetime.strptime(str(ephem.date(next_setting)), ephem_format) + timedelta(seconds=1)
    for time in range(int(round(start_time.timestamp())), int(round(end_time.timestamp())), 60*60*24):
        observer.date = datetime.fromtimestamp(time)
        next_rising = datetime.strptime(str(ephem.date(observer.next_rising(target))), ephem_format)
        next_setting = datetime.strptime(str(ephem.date(observer.next_setting(target))), ephem_format)
    return rise_set