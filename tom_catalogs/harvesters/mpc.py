import re
import logging
import requests
from math import sqrt, degrees

from astropy.constants import GM_sun, au
from tom_catalogs.harvester import AbstractHarvester

from astroquery.mpc import MPC

logger = logging.getLogger(__name__)
# logger.setLevel(logging.DEBUG)


class MPCHarvester(AbstractHarvester):
    """
    The ``MPCHarvester`` is the interface to the Minor Planet Center catalog. For information regarding the Minor Planet
    Center catalog, please see https://minorplanetcenter.net/ or
    https://astroquery.readthedocs.io/en/latest/mpc/mpc.html.
    """

    name = 'MPC'

    def query(self, term):
        self._object_type = 'asteroid'
        self._query_type = 'name'
        numbered_object = re.compile(r'(\d+)(P?)\s*$')
        provisional_desig = re.compile(r'^\s*(\d{4}\s*[A-Z]{2}\d*)')
        provisional_comets = re.compile(r'([C,P,A,D]/\d{4} [A-H,J-Y]{1,2}\d+)')

        match = re.search(provisional_desig, term)
        if match:
            logger.debug("Desig match")
            self._query_type = 'desig'
            self._object_term = match.groups()[0]
            logger.debug(self._object_term, self._object_type)
            self.catalog_data = MPC.query_object(self._object_type, designation=self._object_term)
        else:
            match = re.search(provisional_comets, term)
            if match:
                logger.debug("Comet match")
                self._object_type = 'comet'
                self._query_type = 'desig'
                self._object_term = match.groups()[0]
                self.catalog_data = MPC.query_object(self._object_type, designation=self._object_term)
            else:
                match = re.search(numbered_object, term)
                if match:
                    # Numbered object (asteroid or comet)
                    logger.debug("Num Match")
                    self._object_term = match.groups()[0]
                    self._query_type = 'number'
                    if match.groups()[1] == 'P':
                        # Periodic comet
                        self._object_type = 'comet'
                        self._object_term = ''.join(match.groups())
                    self.catalog_data = MPC.query_object(self._object_type, number=self._object_term)
                else:
                    logger.debug("No match")
                    self._object_term = term
                    self.catalog_data = MPC.query_object(self._object_type, name=self._object_term)

    def to_target(self):
        target = super().to_target()
        result = self.catalog_data[0]
        target.type = 'NON_SIDEREAL'
        if result.get('number', None) is not None:
            if result.get('name', None) is not None:
                target.name = str(result['number'])
                target.extra_names = [str(result['name']), ]
                target.extra_names += [result['designation']] if result['designation'] else []
            else:
                target.name = str(result['number'])
                if result.get('object_type'):
                    # Add comet object type if it exists
                    target.name += result['object_type']
        else:
            target.name = result['designation']
        target.epoch_of_elements = self.jd_to_mjd(result['epoch_jd'])
        target.arg_of_perihelion = float(result['argument_of_perihelion'])
        target.eccentricity = float(result['eccentricity'])
        target.lng_asc_node = float(result['ascending_node'])
        target.inclination = float(result['inclination'])
        target.mean_daily_motion = float(result['mean_daily_motion'])
        object_type = result.get('object_type', '')
        target.scheme = 'MPC_MINOR_PLANET'
        if object_type == 'C' or object_type == 'P':
            target.scheme = 'MPC_COMET'
            target.perihdist = float(result['perihelion_distance'])
            try:
                # Convert JD to MJD as string (avoid losing precision)
                target.epoch_of_perihelion = float(result['perihelion_date_jd'][2:]) - 0.5
            except ValueError:
                raise
        else:
            target.mean_anomaly = float(result['mean_anomaly'])
            target.semimajor_axis = float(result['semimajor_axis'])
            target.abs_mag = float(result['absolute_magnitude'])
            target.slope = float(result.get('phase_slope', 0.15))
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
        if isinstance(result, list):
            result = result[0]

        target.type = 'NON_SIDEREAL'
        target.scheme = 'MPC_COMET'

        unpacked_primary_desig = result['designation_data']['unpacked_primary_provisional_designation']
        orbfit_name = result['designation_data']['orbfit_name']
        # If the unpacked primary designation (minus any spaces in the middle) is the same as the orbfit_name,
        # then we have a provisional-only and no permanent designation. In this case, set the target's name
        # to the unpacked primary designation (with the space). Otherwise we have a permanent desigination,
        # and it's safe (hopefully) to use the orbfit_name without having to unpack into year & half-month plus
        # running designation
        target_name = None
        if unpacked_primary_desig.replace(' ', '') == orbfit_name:
            target_name = unpacked_primary_desig
        else:
            target_name = orbfit_name
        target.name = target_name
        extra_desigs = []
        if result['designation_data'].get('name', "") != "":
            extra_desigs.append(result['designation_data']['name'])
        extra_desigs.append(unpacked_primary_desig)
        extra_desigs += result['designation_data']['unpacked_secondary_provisional_designations']
        # Make sure we don't include the primary designation twice
        try:
            extra_desigs.remove(target.name)
        except ValueError:
            pass
        target.extra_names = extra_desigs

        # Get magnitude data
        target.abs_mag = result['magnitude_data']['H']
        target.slope = result['magnitude_data']['G']

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
