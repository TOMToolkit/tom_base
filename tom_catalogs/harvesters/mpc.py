import requests
from math import sqrt, degrees

from astropy.constants import GM_sun, au
from tom_catalogs.harvester import AbstractHarvester

from astroquery.mpc import MPC


class MPCHarvester(AbstractHarvester):
    """
    The ``MPCHarvester`` is the interface to the Minor Planet Center catalog. For information regarding the Minor Planet
    Center catalog, please see https://minorplanetcenter.net/ or
    https://astroquery.readthedocs.io/en/latest/mpc/mpc.html.
    """

    name = 'MPC'

    def query(self, term):
        self.catalog_data = MPC.query_object('asteroid', name=term)

    def to_target(self):
        target = super().to_target()
        result = self.catalog_data[0]
        target.type = 'NON_SIDEREAL'
        target.name = result['name']
        target.extra_names = [result['designation']] if result['designation'] else []
        target.epoch_of_elements = self.jd_to_mjd(result['epoch_jd'])
        target.mean_anomaly = result['mean_anomaly']
        target.arg_of_perihelion = result['argument_of_perihelion']
        target.eccentricity = result['eccentricity']
        target.lng_asc_node = result['ascending_node']
        target.inclination = result['inclination']
        target.mean_daily_motion = result['mean_daily_motion']
        target.semimajor_axis = result['semimajor_axis']
        return target


class MPCExplorerHarvester(AbstractHarvester):
    """
    The ``MPCExplorerHarvester`` is the new API interface to the Minor Planet Center catalog.
    For information regarding the Minor Planet Center catalog, please see:
    https://minorplanetcenter.net/ or
    https://minorplanetcenter.net/mpcops/documentation/orbits-api/
    To enable this for use, add 'tom_catalogs.harvesters.mpc.MPCExplorerHarveter',
    into TOM_HARVESTER_CLASSES in your TOM's settings.py
    """

    name = 'MPC Explorer'
    # Gaussian gravitational constant
    _k = degrees(sqrt(GM_sun.value) * au.value**-1.5 * 86400.0)

    def query(self, term):
        self.catalog_data = None
        response = requests.get("https://data.minorplanetcenter.net/api/get-orb", json={"desig": term})
        if response.ok:
            response_data = response.json()
            if len(response_data) >= 2 and response_data[0] is not None and 'mpc_orb' in response_data[0]:
                # Format currently seems to be a 2-length list with 0th element containing
                # MPC_ORB.JSON format date and a status code in the 1th element. I suspect
                # there may be extra entries for e.g. comets, but these are not present in MPC Explorer yet
                # Store everything other than the status code for now and for later parsing.
                self.catalog_data = response.json()[0:-1]

    def to_target(self):
        target = super().to_target()
        result = self.catalog_data[0]['mpc_orb']

        target.type = 'NON_SIDEREAL'
        target.scheme = 'MPC_COMET'
        target.name = result['designation_data']['iau_designation'].replace('(', '').replace(')', '')
        extra_desigs = []
        if result['designation_data'].get('name', "") != "":
            extra_desigs.append(result['designation_data']['name'])
        extra_desigs.append(result['designation_data']['unpacked_primary_provisional_designation'])
        extra_desigs += result['designation_data']['unpacked_secondary_provisional_designations']
        # Make sure we don't include the primary designation twice
        try:
            extra_desigs.remove(target.name)
        except ValueError:
            pass
        target.extra_names = extra_desigs

        target.epoch_of_elements = result['epoch_data']['epoch']
        # Map coefficients to elements
        element_names = result['COM']['coefficient_names']
        element_values = result['COM']['coefficient_values']
        target.arg_of_perihelion = element_values[element_names.index('argperi')]
        target.eccentricity = element_values[element_names.index('e')]
        target.lng_asc_node = element_values[element_names.index('node')]
        target.inclination = element_values[element_names.index('i')]
        target.perihdist = element_values[element_names.index('q')]
        target.epoch_of_perihelion = element_values[element_names.index('peri_time')]
        # These need converters
        if result['categorization']['object_type_int'] != 10 and \
                result['categorization']['object_type_int'] != 11:
            # Don't do for comets... (Object type #'s from:
            # https://minorplanetcenter.net/mpcops/documentation/object-types/ )
            target.scheme = 'MPC_MINOR_PLANET'
            try:
                target.semimajor_axis = target.perihdist / (1.0 - target.eccentricity)
                if target.semimajor_axis < 0 or target.semimajor_axis > 1000.0:
                    target.semimajor_axis = None
            except ZeroDivisionError:
                target.semimajor_axis = None
            if target.semimajor_axis:
                target.mean_daily_motion = self._k / (target.semimajor_axis * sqrt(target.semimajor_axis))
            if target.mean_daily_motion:
                td = target.epoch_of_elements - target.epoch_of_perihelion
                mean_anomaly = td * target.mean_daily_motion
                # Normalize into 0...360 range
                mean_anomaly = mean_anomaly % 360.0
                if mean_anomaly < 0.0:
                    mean_anomaly += 360.0
                target.mean_anomaly = mean_anomaly

        return target
