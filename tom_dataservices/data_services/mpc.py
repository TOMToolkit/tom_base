from math import sqrt, degrees
from typing import List, Dict
import logging

import requests
from django import forms
from astropy.constants import GM_sun, au
from astroquery.exceptions import RemoteServiceError

from tom_dataservices.dataservices import DataService
from tom_dataservices.forms import BaseQueryForm
from tom_targets.models import Target

logger = logging.getLogger(__name__)


class MPCExplorerDataService(DataService):
    """
    This the MPCExplorer dataservice is responsible for querying MPC for an object ID.
    This uses the newer API interface to the Minor Planet Center catalog.
    For information regarding the Minor Planet Center catalog, please see:
    https://minorplanetcenter.net/ (overview of MPC) or
    https://data.minorplanetcenter.net/explorer/ (MPC Explorer) or
    https://minorplanetcenter.net/mpcops/documentation/orbits-api/ (API documentation).
    Uses requests.
    """

    name = 'MPC Explorer'
    verbose_name = 'Minor Planet Center Explorer'
    info_url = 'https://data.minorplanetcenter.net/explorer/'
    query_results_table = "tom_dataservices/mpc/partials/mpc_results_table.html"

    # Gaussian gravitational constant
    _k = degrees(sqrt(GM_sun.value) * au.value**-1.5 * 86400.0)

    @classmethod
    def get_form_class(cls):
        """
        Points to the form class discussed below.
        """
        return MPCForm

    def build_query_parameters(self, parameters: Dict, **kwargs) -> Dict:
        """
        Use this function to convert the form results into the query parameters understood
        by the Data Service.
        """
        query_parameters = {
            'desig': parameters.get('designation')
        }

        self.query_parameters = query_parameters
        return query_parameters

    def build_query_parameters_from_target(self, target, **kwargs):
        """
        This is a method that builds query parameters based on an existing target object that will be recognized by
        `query_service()`.
        This is done by reproducing the single parameter uniquely for
        a target query.

        :param target: A target object to be queried
        :return: query_parameters (usually a dict) that can be understood by `query_service()`
        """

        query_parameters = {
            'designation': target.name
        }

        return query_parameters

    def query_service(self, query_parameters: Dict, **kwargs):
        """
        This is where you actually make the call to the Data Service.
        Return the results.
        """

        try:
            query_results = {}
            response = requests.get("https://data.minorplanetcenter.net/api/get-orb", json=query_parameters)
            if response.ok:
                response_data = response.json()
                if len(response_data) >= 2 and response_data[0] is not None and 'mpc_orb' in response_data[0]:
                    # Format currently seems to be a 2-length list with 0th element containing
                    # MPC_ORB.JSON format data and a status code in element 1. I suspect
                    # there may be extra entries for e.g. comets, but these are not present in MPC Explorer yet
                    # Store everything other than the status code for now and for later parsing.
                    query_results = response.json()[0:-1][0]['mpc_orb']
        except RemoteServiceError:
            query_results = {}
        self.query_results = query_results
        return self.query_results

    def query_targets(self, query_parameters: Dict, **kwargs) -> List[Dict]:
        """
        This code calls `query_service` and returns a list of dicts containing target results.
        This call and the results should be tailored towards describing targets.
        """
        query_results = self.query_service(query_parameters)
        logger.debug(f"Query results: {query_results}")
        targets = []
        for target in query_results:
            # The MPC Explorer API currently returns a single target per query, but we return a list
            target['mpc_orb'] = query_results[0] if query_results else []
            target['name'] , target['aliases'] = self.get_additional_mpc_names(target['mpc_orb'])
            targets.append(target)

        return targets

    def get_additional_mpc_names(self, query_result):
        """
        We want to sort out the different names that are returned from the MPC and select the best one as
        the primary designation stored in target.name
        """
        aliases = []
        unpacked_primary_desig = query_result['designation_data']['unpacked_primary_provisional_designation']
        orbfit_name = query_result['designation_data']['orbfit_name']
        # If the unpacked primary designation (minus any spaces in the middle) is the same as the orbfit_name,
        # then we have a provisional-only and no permanent designation. In this case, set the target's name
        # to the unpacked primary designation (with the space). Otherwise we have a permanent designation,
        # and it's safe (hopefully) to use the orbfit_name without having to unpack into year & half-month plus
        # running designation
        target_name = None
        if unpacked_primary_desig.replace(' ', '') == orbfit_name:
            target_name = unpacked_primary_desig
        else:
            target_name = orbfit_name
        primary_name = target_name
        if query_result['designation_data'].get('name', "") != "":
            aliases.append(query_result['designation_data']['name'])
        aliases.append(unpacked_primary_desig)
        aliases += query_result['designation_data']['unpacked_secondary_provisional_designations']
        # Make sure we don't include the primary designation twice
        try:
            aliases.remove(primary_name)
        except ValueError:
            pass

        return primary_name, aliases

    def create_target_from_query(self, target_result: Dict, **kwargs):
        """Create a new target from the query results
        :returns: target object
        :rtype: `Target`
        """

        result = target_result['mpc_orb']
        if isinstance(result, list):
            result = result[0]

        target = Target()
        target.name = target_result['name']
        target.type = Target.NON_SIDEREAL
        target.scheme = 'MPC_COMET'

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


class MPCForm(BaseQueryForm):
    designation = forms.CharField(
        required=False,
        label='Designation',
        help_text='Solar System Object Name (e.g. Bennu, A1234, 1, 67P, K23A00B, 2024 AA, 2019JD24, C/2019 Y4)'
    )
