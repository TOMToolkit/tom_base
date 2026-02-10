import logging
from typing import Any, Dict, List

from django import forms

from tom_dataservices.dataservices import DataService
from tom_dataservices.forms import BaseQueryForm as QueryForm
from tom_targets.models import Target, TargetName

from astroquery.simbad import Simbad
from astropy.table import Table

logger = logging.getLogger(__name__)
# logger.setLevel(logging.DEBUG)


class SimbadDataService(DataService):
    """
    The ``SimbadDataService`` is the interface to the SIMBAD catalog. At present, it is only queryable by identifier.
    For information regarding identifier format, please see http://simbad.u-strasbg.fr/simbad/sim-fid or
    https://astroquery.readthedocs.io/en/latest/simbad/simbad.html.
    """
    name = 'Simbad'

    def __init__(self, *args, **kwargs):
        self.simbad = Simbad()
        self.simbad.add_votable_fields('pmra', 'pmdec', 'ra', 'dec', 'main_id', 'parallax', 'distance')

    @classmethod
    def get_form_class(cls):
        return SimbadForm

    def build_query_parameters(self, parameters, **kwargs):
        """
        Use this function to convert the form results into the query parameters understood
        by the Data Service.
        """
        logger.debug(f'SIMBAD.build_query_parameters: parameters {parameters}')
        self.query_parameters = parameters
        return self.query_parameters

    def query_service(self, query_parameters, **kwargs):
        """
        This is where you actually make the call to the Data Service,
        in this case Simbad.

        Return the results.
        """
        logger.debug(f'SIMBAD.query_service.query_parameters {query_parameters}')
        # Get search term from query parameters
        search_term: str = query_parameters.get('search_term', '')  # TODO: what default???

        # Simbad returns an astropy.table.Table
        catalog_data: Table = self.simbad.query_object(search_term)  # type: ignore
        logger.debug(f'SIMBAD.query_service.catalog_data{catalog_data}')

        # astroquery <0.4.10, > 0.4.7 has issues joining the distance field, failing to find any results.
        # This workaround checks if the query result is an empty table and then tries the query a 2nd time without the
        # distance field.
        if not catalog_data:
            self.simbad.reset_votable_fields()
            self.simbad.add_votable_fields('pmra', 'pmdec', 'ra', 'dec', 'main_id', 'parallax')
            catalog_data = self.simbad.query_object(search_term)  # type: ignore
            logger.debug(f'SIMBAD.query_service (reset) catalog_data{catalog_data}')

        self.query_results = catalog_data
        return self.query_results

    def query_targets(self, query_parameters, **kwargs) -> List[Dict[str, Any]]:
        """
        Query SIMBAD and convert results to target data dictionaries.

        Queries the SIMBAD catalog using the provided parameters, then transforms
        the returned astropy Table into a list of dictionaries containing target
        information suitable for target creation.

        :param query_parameters: Dictionary of query parameters collected from SimbadForm
        :type query_parameters: dict
        :param kwargs: Additional keyword arguments passed to query_service
        :type kwargs: dict

        :return: List of dictionaries; one dict for each row, Table.colnames are keys
        :rtype: List[Dict[str, Any]]
        """
        # do the actual SIMBAD via query_service
        target_table: Table = self.query_service(query_parameters, **kwargs)

        # these are the fields (==table columns==dict keys) that we keep
        votable_fields = ['ra', 'dec', 'pmra', 'pmdec', 'main_id', 'mesdistance.dist', 'mesdistance.unit']
        # convert astroquery.table.Table to list of target dict (keeping only votable_fields)
        targets: List[Dict[str, Any]] = [
            {key: row[key] for key in votable_fields if key in target_table.colnames}
            for row in target_table]

        # add name and alias items to each target
        for target in targets:
            target['name'] = target['main_id']
            # if the returned target name (main_id) was not the search term, make the main_id the alias
            if query_parameters['search_term'] != target['main_id']:
                target['name'] = query_parameters['search_term']  # and make the search term the name
                target['aliases'] = [str(target['main_id']).replace(' ', '')]  # remove whitespace

        return targets

    def create_target_from_query(self, target_result: Dict[str, Any], **kwargs) -> Target:
        """Create a new target from the query results. This method will be called from
        `SimbadDataService.to_target()` via `DataService.CreateTargetFromQueryView.post()`.

        :param target_result: Dictionary containing target data. For example:
         ```python
         {
             'ra': np.float64(350.8584),
             'dec': np.float64(58.8113),
             'pmra': masked,
             'pmdec': masked,
             'main_id': 'NAME Cas A',
             'mesdistance.dist': np.float64(3.4),
             'mesdistance.unit': 'kpc ',
             'name': 'Cas A',
             'alias': 'alias for CasA',
             'id': 0
             }
        ```
        :type target_result: Dict[str, Any]
        :param kwargs: Additional keyword arguments
        :type kwargs: dict

        :return: Unsaved Target instance populated with SIMBAD data
        :rtype: Target
        """
        target = Target(
            name=target_result['name'],
            type='SIDEREAL',
            ra=target_result['ra'],
            dec=target_result['dec'],
            pm_ra=target_result['pmra'],
            pm_dec=target_result['pmdec'],
        )

        # Convert all distances to pc
        target_distance = target_result.get('mesdistance.dist', None)
        if target_distance and 'kpc' in target_result.get('mesdistance.unit', ''):
            target.distance = target_distance * 1000  # kilo
        elif target_distance and 'mpc' in target_result.get('mesdistance.unit', ''):
            target.distance = target_distance * 1000000  # mega

        return target  # not saved yet

    def create_aliases_from_query(self, alias_results, **kwargs) -> List[TargetName]:
        """
        The query_result is a target dictionary created by query_targets()
        It has name and alias fields. Use the name to get the Target and give it
        the alias.
        """
        aliases = []
        for alias in alias_results:
            aliases.append(TargetName(name=alias))

        return aliases  # not saved yet


class SimbadForm(QueryForm):
    search_term = forms.CharField(
        required=False,
        widget=forms.TextInput(
            attrs={'placeholder': 'Target name, e.g. Arcturus'}
        ),
    )
