from django import forms
from django.test import TestCase

from tom_dataservices.dataservices import BaseDataService, MissingDataException
from tom_dataservices.forms import BaseQueryForm


test_query_results = {'ra': 24, 'dec': 77, 'name': 'faketarget', 'type': 'SIDEREAL'}


class TestDataServiceForm(BaseQueryForm):
    """ All brokers must have a form which will be used to construct and save queries
    to the broker. They should subclass `BaseQueryForm` which includes some required
    fields and contains logic for serializing and persisting the query parameters to the
    database. This test form will only have one field.
    """
    name = forms.CharField(required=True)


class TestDataService(BaseDataService):
    name = 'TEST'
    service_notes = "This is a test DataService."

    def query_service(self, term):
        if term == 'notfound':
            raise MissingDataException
        self.query_results = test_query_results

    def get_form_class(self):
        return TestDataServiceForm

    def pre_query_validation(self, query_parameters):
        pass

    def to_target(self, query_results):
        target = super().to_target(query_results)
        target.name = query_results['name']
        target.type = query_results['type']
        target.ra = query_results['ra']
        target.dec = query_results['dec']
        return target


class TestDataServiceClass(TestCase):
    """
    Test the functionality of the TestDataService.
    """

    def test_to_target(self):
        target = TestDataService.to_target(self, test_query_results)
        self.assertEqual(target.name, test_query_results['name'])
