from math import sqrt, degrees

from astropy.constants import GM_sun, au
import requests


from tom_dataservices.dataservices import BaseDataService
from tom_dataservices.forms import BaseQueryForm
from tom_targets.models import Target

class ScoutDataService(BaseDataService):
    """
    Docstring for ScoutDataService
    """
    name = 'Scout'
    info_url = 'https://cneos.jpl.nasa.gov/scout/intro.html'
    # Gaussian gravitational constant
    _k = degrees(sqrt(GM_sun.value) * au.value**-1.5 * 86400.0)

    def build_query_parameters(self, parameters, **kwargs):
        """
        Args:
            parameters: dictionary containing either:

            - optional cutoff parameters 

            - Scout name e.g. 'P10vY9r'

        Returns:
            json containing parameters for querying the Scout API.
        """
        return super().build_query_parameters(parameters, **kwargs)

    def create_target_from_query(self, target_results, **kwargs):
        """
            Returns a Target instance for an object defined by a query result,

            :returns: target object
            :rtype: `Target`
        """

        # Construct dictionary from ['orbits']['fields'] and ['orbits']['data'][0]
        elements =  dict(zip(target_results['orbits']['fields'], target_results['orbits']['data'][0]))

        target = Target(
            name=target_results['objectName'],
            type='NON-SIDEREAL',
            scheme='MPC_MINOR_PLANET',
            arg_of_perihelion=elements['w'],
            lng_asc_node=elements['om'],
            inclination=elements['inc'],
            eccentricity=elements['ec'],
            epoch_of_elements=float(elements['epoch'][2:]) - 0.5,
            epoch_of_perihelion=float(elements['tp'][2:]) - 0.5,
            perihdist=elements['qr'],
            abs_mag=elements['H'],
            slope=elements.get('G', 0.15) # Never actually present ?
        )
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
