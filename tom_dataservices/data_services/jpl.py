from math import sqrt, degrees

from astropy.constants import GM_sun, au
from django import forms
import logging
import requests
# import pprint

from tom_dataservices.dataservices import DataService
from tom_dataservices.forms import BaseQueryForm
from tom_targets.models import Target

logger = logging.getLogger(__name__)


class ScoutForm(BaseQueryForm):
    tdes = forms.CharField(required=False,
                           label='NEOCP temporary designation')
    neo_score_min = forms.IntegerField(required=False, min_value=0, max_value=100,
                                       label='Minimum NEO digest score (0..100)',
                                       help_text='Minimum NEO digest score (0..100) permissible')
    pha_score_min = forms.IntegerField(required=False, min_value=0, max_value=100,
                                       label='Minimum PHA digest score (0..100)',
                                       help_text='Minimum PHA digest score (0..100) permissible')
    geo_score_max = forms.IntegerField(required=False, initial=5, min_value=0, max_value=100,
                                       label='Maximum GEO digest score (0..100)',
                                       help_text='Maximum Geocentric digest score (0..100) permissible')
    help_text = 'Rating to character the chances of an Earth impact '
    help_text += '(0=negligible, 1=small, 2=modest, 3=moderate, 4=elevated)'
    impact_rating_min = forms.IntegerField(required=False, min_value=0, max_value=4,
                                           label='Minimum impact rating (0..4)',
                                           help_text=help_text)
    ca_dist_min = forms.FloatField(required=False,
                                   label='Minimum CA distance (LD)',
                                   help_text='Minimum close approach distance (lunar distances)')
    pos_unc_min = forms.FloatField(required=False,
                                   label='Minimum positional uncertainty (arcmin)')
    pos_unc_max = forms.FloatField(required=False,
                                   label='Maximum positional uncertainty (arcmin)')


class ScoutDataService(DataService):
    """
    Docstring for ScoutDataService
    """
    name = 'Scout'
    app_version = '0.0.3'
    info_url = 'https://cneos.jpl.nasa.gov/scout/intro.html'
    query_results_table = 'tom_dataservices/scout/partials/scout_query_results_table.html'
    expected_signature = {'source': 'NASA/JPL Scout API', 'version': '1.3'}
    total_results = None

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

    def get_simple_form_partial(self):
        return 'tom_dataservices/scout/partials/scout_simple_form.html'

    def get_advanced_form_partial(self):
        return 'tom_dataservices/scout/partials/scout_advanced_form.html'

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

        # Save a copy of the input form parameters for later use as there are some parameters that are used in the
        # query_targets method that are not part of the query to the Scout API.
        # But don't save and overwrite later versions which don't have the form parameters (eg. when running
        # query_targets with the tdes parameter set to a Scout name).
        if 'neo_score_min' in parameters:
            self.input_parameters = parameters
            # pprint.pprint(parameters, indent=2)

        if parameters.get('tdes') is not None and parameters['tdes'] != '':
            data['tdes'] = parameters['tdes']

            # Return at least one orbit
            data['orbits'] = 1
            data['n-orbits'] = 1
        self.query_parameters = data
        return data

    def query_service(self, data, **kwargs):
        """Make call to the JPL Scout service

        :param data: Dictionary containing query parameters for the Scout API.
        :type data: dict
        :return: json containing response from Scout API.
        :rtype: dict
        """
        response = requests.get(self.get_urls(url_type='search_url'), data)

        response.raise_for_status()
        json_response = response.json()
        if json_response is not None and 'error' not in json_response:
            if json_response['signature'] == self.expected_signature:
                if 'data' in json_response:
                    self.query_results = json_response['data']
                    self.total_results = int(json_response.get('count', 0))
                else:
                    # Per-object data has different structure, make it into a list of 1 target
                    # so the the `for result in results` in `query_targets()` iterates (once..)
                    # over the target(s) and not over the keys of a single target
                    self.query_results = [json_response, ]
                    if self.total_results is None:
                        self.total_results = 1
            else:
                msg = "Signature of response from Scout API does not match expected signature. "
                msg += f"Expected {self.expected_signature}, got {json_response['signature']}."
                logger.warning(msg)
        else:
            self.query_results = None
            msg = "Error retrieving data from Scout."
            if data.get('tdes', '') != '':
                msg += f" Object {data['tdes']} is no longer on Scout."
            logger.warning(msg)
        return self.query_results

    def query_targets(self, query_parameters, **kwargs):
        """Set up and run a specialized query for retrieving targets from a DataService."""
        results = self.query_service(self.build_query_parameters(query_parameters))

        targets = []
        if results is not None and 'error' not in results:
            neo_score_min = 0
            if self.input_parameters.get('neo_score_min', 0) is not None:
                neo_score_min = self.input_parameters['neo_score_min']
            pha_score_min = 0
            if self.input_parameters.get('pha_score_min', 0) is not None:
                pha_score_min = self.input_parameters['pha_score_min']
            geo_score_max = 101
            if self.input_parameters.get('geo_score_max', 101) is not None:
                geo_score_max = self.input_parameters['geo_score_max']
            # Might be None if we want all objects irrespective of impact chance
            impact_rating_min = self.input_parameters['impact_rating_min']
            ca_dist_min = self.input_parameters['ca_dist_min']
            pos_unc_min = 0
            if self.input_parameters.get('pos_unc_min', 0) is not None:
                pos_unc_min = self.input_parameters['pos_unc_min']
            pos_unc_max = 360 * 60   # 360 degrees (whole sky) as arcmin
            if self.input_parameters.get('pos_unc_max', pos_unc_max) is not None:
                pos_unc_max = self.input_parameters['pos_unc_max']

            for result in results:
                # Filter on the many, many form parameters.
                try:
                    pos_unc = float(result['unc'])
                except ValueError:
                    pos_unc = 0.0
                try:
                    ca_dist = float(result['caDist'])
                except TypeError:
                    ca_dist = None
                # print("neoScore phaScore, geoScore, rating, caDist, posuncmin, posuncmax")
                # print(result['neoScore'] >= neo_score_min, result['phaScore'] >= pha_score_min,
                #       result['geocentricScore'] < geo_score_max,
                #       ((result['rating'] is not None and
                #           impact_rating_min is not None and
                #           result['rating'] >= impact_rating_min) or
                #        impact_rating_min is None),
                #       (ca_dist_min is None or
                #       (ca_dist_min is not None and ca_dist is not None and ca_dist <= ca_dist_min)),
                #       pos_unc >= pos_unc_min, pos_unc <= pos_unc_max)
                if result['neoScore'] >= neo_score_min and result['phaScore'] >= pha_score_min and \
                        result['geocentricScore'] < geo_score_max and \
                        ((result['rating'] is not None and
                          impact_rating_min is not None and
                          result['rating'] >= impact_rating_min
                          ) or
                         impact_rating_min is None) and \
                        (ca_dist_min is None or
                         (ca_dist_min is not None and ca_dist is not None and ca_dist <= ca_dist_min)) and \
                        pos_unc >= pos_unc_min and pos_unc <= pos_unc_max:
                    if 'orbits' in result:
                        # This was a query for a specific target so we already have the needed info
                        target_data = result
                    else:
                        # Fetch per-target data
                        query_parameters['tdes'] = result['objectName']
                        target_parameters = self.build_query_parameters(query_parameters)
                        target_data = self.query_service(target_parameters, url=self.get_urls('object_url'))
                        if target_data is not None:
                            target_data = target_data[0]
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

    def get_additional_context_data(self, **kwargs):
        """Add additional context data for rendering the query results template."""
        context = {}

        context['total_results'] = self.total_results if self.total_results is not None else 0
        context['neo_score_min'] = self.input_parameters.get('neo_score_min', 0)
        context['pha_score_min'] = self.input_parameters.get('pha_score_min', 0)
        context['geo_score_max'] = self.input_parameters.get('geo_score_max', 5)
        return context

    def create_target_from_query(self, target_results, **kwargs):
        """
            Returns a Target instance for an object defined by a query result,

            :returns: target object
            :rtype: `Target`
        """

        # Construct dictionary from ['orbits']['fields'] and ['orbits']['data'][0]
        elements = dict(zip(target_results['orbits']['fields'], target_results['orbits']['data'][0]))

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
            slope=elements.get('G', 0.15)  # Never actually present ?
        )
        try:
            target.semimajor_axis = target.perihdist / (1.0 - target.eccentricity)
            if target.semimajor_axis < 0 or target.semimajor_axis > 1000.0:
                target.semimajor_axis = None
        except (ZeroDivisionError, ValueError):
            target.semimajor_axis = None
        if target.semimajor_axis:
            target.mean_daily_motion = self._k / (target.semimajor_axis * sqrt(target.semimajor_axis))
        if target.mean_daily_motion and target.epoch_of_elements and target.epoch_of_perihelion:
            td = target.epoch_of_elements - target.epoch_of_perihelion
            mean_anomaly = td * target.mean_daily_motion
            # Normalize into 0...360 range
            mean_anomaly = mean_anomaly % 360.0
            if mean_anomaly < 0.0:
                mean_anomaly += 360.0
            target.mean_anomaly = mean_anomaly
        return target
