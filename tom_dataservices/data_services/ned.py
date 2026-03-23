from django import forms
from astroquery.ned import Ned
from astroquery.exceptions import RemoteServiceError


from tom_dataservices.dataservices import DataService
from tom_dataservices.forms import BaseQueryForm

from tom_targets.models import Target


class NEDDataService(DataService):
    """
    This is an Example Data Service with the minimum required
    functionality.
    """
    name = 'NED'

    @classmethod
    def get_form_class(cls):
        """
        Points to the form class discussed below.
        """
        return NEDForm

    def build_query_parameters(self, parameters, **kwargs):
        """
        Use this function to convert the form results into the query parameters understood
        by the Data Service.
        """
        query_parameters = {
            'object_id': parameters.get('object_id')
        }

        self.query_parameters = query_parameters
        return query_parameters

    def query_service(self, query_parameters, **kwargs):
        """
        This is where you actually make the call to the Data Service.
        Return the results.
        """
        try:
            query_results = Ned.query_object(query_parameters.get('object_id'))
        except RemoteServiceError:
            query_results = {}
        self.query_results = query_results
        return self.query_results

    def query_targets(self, query_parameters, **kwargs):
        """
        This code calls `query_service` and returns a list of dicts containing target results.
        This call and the results should be tailored towards describing targets.
        """
        query_results = self.query_service(query_parameters)
        # Convert astropy table to list of dictionaries
        targets = [dict(zip(query_results.colnames, row)) for row in query_results]
        # Make primary name searched term. Add NED name as alias.
        if query_parameters.get('object_id'):
            for target_result in targets:
                if target_result['Object Name'] != query_parameters['object_id']:
                    target_result['aliases'] = [target_result['Object Name']]
                    target_result['Object Name'] = query_parameters['object_id']
        return targets

    def create_target_from_query(self, target_result, **kwargs):
        """Create a new target from the query results
        :returns: target object
        :rtype: `Target`
        """

        target = Target(
            name=target_result['Object Name'],
            type='SIDEREAL',
            ra=target_result['RA'],
            dec=target_result['DEC'],
        )
        return target

class NEDForm(BaseQueryForm):
    object_id = forms.CharField(required=False,
                                  label='Object ID',
                                  help_text='Extragalactic Source Name (i.e. "NGC 224" or "M31")')