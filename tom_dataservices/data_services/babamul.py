import logging

import requests
from astropy.time import Time, TimezoneInfo
from django import forms
from django.core.exceptions import ValidationError
from django.db.utils import IntegrityError

from tom_dataproducts.models import PhotometryReducedDatum
from tom_dataservices.dataservices import DataService, NotConfiguredError, QueryServiceError
from tom_dataservices.forms import BaseQueryForm
from tom_targets.models import Target, TargetExtra

logger = logging.getLogger(__name__)

ZTF = 'ZTF'
LSST = 'LSST'
DEFAULT_TIMEOUT = 30


class BabamulForm(BaseQueryForm):
    object_id = forms.CharField(required=False,
                                label='Object ID',
                                help_text='Survey object identifier, e.g. "ZTF18aahflzc"')
    ra = forms.FloatField(required=False, min_value=0., max_value=360.,
                          label='R.A.',
                          help_text='Right ascension in degrees')
    dec = forms.FloatField(required=False, min_value=-90., max_value=90.,
                           label='Dec.',
                           help_text='Declination in degrees')
    radius = forms.FloatField(required=False, min_value=0.,
                              label='Cone Radius',
                              help_text='Search radius in arcseconds')
    limit = forms.IntegerField(required=False, min_value=1,
                               label='Maximum Results',
                               help_text='Leave blank to use the Babamul default')

    def clean_radius(self):
        radius = self.cleaned_data.get('radius')
        if radius is not None and radius <= 0:
            raise forms.ValidationError('Cone Radius must be greater than zero.')
        return radius

    def clean(self):
        cleaned_data = super().clean()
        cone = [cleaned_data.get(field) for field in ['ra', 'dec', 'radius']]
        if not cleaned_data.get('object_id') and not all(value is not None for value in cone):
            raise forms.ValidationError('Please provide either an Object ID, or R.A., Dec. and a Cone Radius.')
        return cleaned_data


class BabamulDataService(DataService):
    """
        The ``BabamulDataService`` is the interface to Babamul, the public service of the BOOM alert broker for
        the ZTF and LSST surveys. For information regarding Babamul, please see https://babamul.caltech.edu/

        An API key is available by signing up at https://babamul.caltech.edu/

        Requires the following configuration in settings.py:

        .. code-block:: python

            DATA_SERVICES = {
                'Babamul': {
                    'api_key': os.getenv('BABAMUL_API_KEY', 'DO NOT COMMIT API TOKENS TO GIT!'),
                    'base_url': 'https://babamul.caltech.edu/api/babamul',
                    'timeout': 30,
                },
            }
    """
    name = 'Babamul'
    verbose_name = 'Babamul Alert Broker'
    info_url = 'https://babamul.caltech.edu/'
    query_results_table = 'tom_dataservices/babamul/partials/babamul_query_results_table.html'

    @classmethod
    def urls(cls, **kwargs) -> dict:
        """Dictionary of URLs for the Babamul API."""
        urls = super().urls()
        urls['base_url'] = cls.get_configuration('base_url', 'https://babamul.caltech.edu/api/babamul')
        urls['objects_url'] = f'{urls["base_url"]}/objects'
        urls['object_url'] = f'{urls["base_url"]}/surveys/{{survey}}/objects/{{object_id}}'
        return urls

    def build_headers(self, *args, **kwargs):
        """Babamul authenticates with a bearer token supplied at signup."""
        # get_credentials() raises NotConfiguredError when DATA_SERVICES has no entry for this service;
        # it returns None when the entry exists but has no api_key. Both are the same problem to a user,
        # and RunQueryView renders NotConfiguredError with a link to the configuration docs.
        api_key = self.get_credentials()
        if not api_key:
            raise NotConfiguredError(f'No api_key is configured for the {self.name} DataService.')
        return {'Authorization': f'Bearer {api_key}'}

    def build_query_parameters(self, parameters, **kwargs):
        """
        Args:
            parameters: dictionary containing either an ``object_id``, or ``ra``, ``dec`` and ``radius``.
                Radius is given in arcseconds. An optional ``limit`` caps the number of results.

        Returns:
            dictionary of query parameters understood by the Babamul API.
        """
        if parameters.get('object_id'):
            query_parameters = {'object_id': parameters['object_id']}
        else:
            query_parameters = {
                'ra': parameters.get('ra'),
                'dec': parameters.get('dec'),
                'radius': parameters.get('radius'),
            }

        if parameters.get('limit'):
            query_parameters['limit'] = parameters['limit']

        self.query_parameters = query_parameters
        return query_parameters

    def build_query_parameters_from_target(self, target, **kwargs):
        """
        Determine which survey to query for an existing target. The survey recorded when the target was
        created is authoritative; otherwise it is inferred from the object id prefix. Targets belonging to
        neither survey are not queried, since Babamul only serves ZTF and LSST.
        """
        try:
            survey = target.targetextra_set.get(key='survey').value
        except TargetExtra.DoesNotExist:
            survey = ZTF if target.name.upper().startswith(ZTF) else None

        if survey is None:
            logger.debug(f'{target.name} does not look like a Babamul object, skipping.')
            return {}
        return {'object_id': target.name, 'survey': survey}

    def query_service(self, query_parameters, **kwargs):
        """Query Babamul and return the payload under the response's ``data`` key."""
        url = kwargs.get('url', self.get_urls('objects_url'))
        try:
            response = requests.get(url,
                                    params=query_parameters,
                                    headers=self.build_headers(),
                                    timeout=self.get_configuration('timeout', DEFAULT_TIMEOUT))
            response.raise_for_status()
            payload = response.json()
        except requests.exceptions.RequestException as e:
            raise QueryServiceError(f'Error querying Babamul: {e}')
        except ValueError:
            raise QueryServiceError(f'Babamul returned a response that could not be parsed as JSON: {url}')

        if not isinstance(payload, dict) or 'data' not in payload:
            raise QueryServiceError(f'Babamul response did not contain a data key: {url}')

        self.query_results = payload['data']
        return self.query_results

    def query_targets(self, query_parameters, **kwargs):
        """Set up and run a specialized query for retrieving targets from Babamul."""
        self.target_results = self.query_service(query_parameters, url=self.get_urls('objects_url'))
        return self.target_results

    def query_photometry(self, query_parameters, **kwargs):
        """
        Retrieve the full object record, which carries the whole light curve: the most recent detection in
        ``candidate``, earlier detections in ``prv_candidates``, and upper limits in ``prv_nondetections``.
        """
        if not query_parameters.get('object_id'):
            return {}
        url = self.get_urls('object_url').format(
            survey=query_parameters.get('survey', ZTF).lower(),
            object_id=query_parameters['object_id'],
        )
        return self.query_service({}, url=url)

    def create_target_from_query(self, target_result, **kwargs):
        """
            Returns a Target instance for an object defined by a query result.

            :returns: target object
            :rtype: `Target`
        """
        return Target(
            name=target_result['objectId'],
            type='SIDEREAL',
            ra=target_result['ra'],
            dec=target_result['dec'],
        )

    def create_target_extras_from_query(self, query_results, **kwargs):
        """
        Fields worth keeping alongside the target. ``distance_arcsec`` is deliberately excluded: it is the
        separation from whichever search position was used, so it is meaningless once the target is saved.
        ``id`` is the result's index in the query cache, injected by the view.
        """
        return {key: value for key, value in query_results.items()
                if key not in ['objectId', 'ra', 'dec', 'distance_arcsec', 'id']}

    def create_reduced_datums_from_query(self, target, data=None, data_type='photometry', **kwargs):
        """
        Create photometry reduced datums from a Babamul object record. Detections come from ``candidate``
        and ``prv_candidates``, and upper limits from ``prv_nondetections``.
        """
        reduced_datums = []
        if not data:
            return reduced_datums

        for detection in self.detections(data):
            reduced_datums.append(self.reduced_datum(
                target, detection,
                brightness=detection['magpsf'],
                brightness_error=detection.get('sigmapsf'),
            ))

        for non_detection in data.get('prv_nondetections') or []:
            if non_detection.get('diffmaglim') is None or not non_detection.get('band'):
                continue
            reduced_datums.append(self.reduced_datum(
                target, non_detection,
                limit=non_detection['diffmaglim'],
            ))

        return reduced_datums

    @staticmethod
    def detections(data):
        """
        The measurements in an object record that carry a magnitude. The most recent detection appears in
        both ``candidate`` and ``prv_candidates``, so measurements are deduplicated by candidate id.
        """
        detections = {}
        for detection in [data.get('candidate')] + list(data.get('prv_candidates') or []):
            if not detection or detection.get('magpsf') is None or not detection.get('band'):
                continue
            key = detection.get('candid', (detection.get('jd'), detection.get('band')))
            detections.setdefault(key, detection)
        return list(detections.values())

    def reduced_datum(self, target, measurement, **values):
        """
        Create or retrieve a single PhotometryReducedDatum. Only the fields covered by the model's
        uniqueness constraint are used to look the datum up; everything else is set on creation, so that a
        later sync reporting a slightly different uncertainty updates nothing rather than failing to match.
        """
        # Babamul reports Julian Date, unlike surveys that report Modified Julian Date.
        timestamp = Time(measurement['jd'], format='jd', scale='utc').to_datetime(TimezoneInfo())
        try:
            reduced_datum, __ = PhotometryReducedDatum.objects.get_or_create(
                target=target,
                timestamp=timestamp,
                bandpass=measurement['band'],
                brightness=values.get('brightness'),
                limit=values.get('limit'),
                defaults={
                    'unit': 'mag',
                    'brightness_error': values.get('brightness_error'),
                    'source_name': self.name,
                }
            )
        except (IntegrityError, ValidationError) as e:
            raise QueryServiceError(f'Error importing ReducedDatum (target:{target} data:{measurement}) -- {e}')
        return reduced_datum

    @classmethod
    def get_form_class(cls):
        return BabamulForm
