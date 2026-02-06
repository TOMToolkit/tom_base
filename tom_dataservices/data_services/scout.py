from math import sqrt, degrees

from astropy.constants import GM_sun, au
from django import forms
from django.contrib import messages
import requests
import pprint

from tom_dataservices.dataservices import BaseDataService
from tom_dataservices.forms import BaseQueryForm
from tom_targets.models import Target

class ScoutForm(BaseQueryForm):
    tdes = forms.CharField(required=False,
                           label='NEOCP temporary designation')
    neo_score_min = forms.IntegerField(required=False, label='Minimum NEO digest score (0..100)')


class ScoutDataService(BaseDataService):
    """
    Docstring for ScoutDataService
    """
    name = 'Scout'
    info_url = 'https://cneos.jpl.nasa.gov/scout/intro.html'
    query_results_table = 'tom_dataservices/scout/partials/scout_query_results_table.html'

    # Gaussian gravitational constant
    _k = degrees(sqrt(GM_sun.value) * au.value**-1.5 * 86400.0)

    @classmethod
    def urls(cls, **kwargs) -> dict:
        """Dictionary of urls for the JPL Scout API (all identical in this case)"""
        urls = super().urls()
        urls['base_url'] = cls.get_configuration('base_url', 'https://ssd-api.jpl.nasa.gov/scout.api')
        urls['object_url'] = urls['base_url']
        urls['search_url'] = urls['base_url']
        return urls

    def build_query_parameters(self, parameters, **kwargs):
        """
        Args:
            parameters: dictionary containing either:

            - optional cutoff parameters 

            - Scout name e.g. 'P10vY9r'

        Returns:
            json containing parameters for querying the Scout API.
        """
        data = {}
        # import pprint
        # pprint.pprint(parameters)
        if parameters.get('tdes') is not None and parameters['tdes'] != '':
            data['tdes'] = parameters['tdes']

            # Return at least one orbit
            data['orbits'] = 1
            data['n-orbits'] = 1
        self.query_parameters = data
        return data

    def query_service(self, data, **kwargs):
        response = requests.get(kwargs['url'], data)
        response.raise_for_status()
        json_response = response.json()
        if 'data' in json_response:
            self.query_results = json_response['data']
        else:
            # Per-object data has different structure
            self.query_results = json_response
        return self.query_results

    def query_targets(self, query_parameters, **kwargs):
        """Set up and run a specialized query for retrieving targets from a DataService."""
        pprint.pprint(query_parameters)
        results = super().query_targets(self.build_query_parameters(query_parameters), url=self.get_urls('search_url'))

        targets = []
        if results is not None and 'error' not in results:
            for result in results:
                if result['neoScore'] >= self.input_parameters.get('neo_score_min', 0):
                    query_parameters['tdes'] = result['objectName']
                    target_parameters = self.build_query_parameters(query_parameters)
                    target_data = self.query_service(target_parameters, url=self.get_urls('object_url'))
                    targets.append(target_data)
        else:
            msg = "Error retrieving data from Scout."
            if query_parameters.get('tdes', '') != '':
                msg += f" Object {query_parameters['tdes']} is no longer on Scout."
            # if request is not None:
            #     messages.error(request, msg)
        return targets

    @classmethod
    def get_form_class(cls):
        return ScoutForm

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
            arg_of_perihelion=float(elements['w']),
            lng_asc_node=float(elements['om']),
            inclination=float(elements['inc']),
            eccentricity=float(elements['ec']),
            epoch_of_elements=float(elements['epoch'][2:]) - 0.5,
            epoch_of_perihelion=float(elements['tp'][2:]) - 0.5,
            perihdist=float(elements['qr']),
            abs_mag=float(elements['H']),
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
