import math

def calculate_zenith(altitude):
    if altitude > 90:
        return 180 - altitude
    elif altitude > 0:
        return 90 - altitude
    else:
        return None

def calculate_airmass(altitude):
    return 1/math.sin((math.radians(altitude) + 244)/(165 + 47*math.pow(math.radians(altitude), 1.1)))