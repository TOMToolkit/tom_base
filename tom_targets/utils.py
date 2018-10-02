import math

def dms_to_dd(value):
        parts = value.split(':')
        return float(parts[0]) + float(parts[1])/60 + float(parts[2])/(60*60)

def dd_to_dms(value):
    is_positive = value >= 0
    value = abs(value)
    minutes,seconds = divmod(value*3600,60)
    degrees,minutes = divmod(minutes,60)
    degrees = degrees if is_positive else -degrees
    return str(degrees) + ':' + str(minutes) + ':' + str(seconds)

def calculate_zenith(altitude):
    if altitude > 90:
        return 180 - altitude
    elif altitude > 0:
        return 90 - altitude
    else:
        return None

def calculate_airmass(altitude):
    return 1/math.sin((math.radians(altitude) + 244)/(165 + 47*math.pow(math.radians(altitude), 1.1)))