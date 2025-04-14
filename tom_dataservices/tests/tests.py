from django import forms
from django.test import TestCase

from tom_dataservices.dataservices import BaseDataService, MissingDataException
from tom_dataservices.forms import BaseQueryForm
from tom_targets.models import Target


test_query_results = {'ra': 24, 'dec': 77, 'name': 'faketarget', 'type': 'SIDEREAL'}


class TestDataServiceForm(BaseQueryForm):
    """ A DataService must implement a form in order to be displayed in a TOM.
    They should subclass `BaseQueryForm`. This test form will only have one field.
    """
    name = forms.CharField(required=True)


class TestDataService(BaseDataService):
    name = 'TEST'
    service_notes = "This is a test DataService."

    def query_service(self, term):
        if term == 'notfound':
            raise MissingDataException
        self.query_results = test_query_results
        return

    def get_form_class(self):
        return TestDataServiceForm

    def create_target_from_query(self, query_results, **kwargs):
        return Target(**query_results)


class EmptyTestDataService(BaseDataService):
    name = 'TEST'
    service_notes = "This is a test DataService."

    def query_service(self, term):
        if term == 'notfound':
            raise MissingDataException
        self.query_results = test_query_results
        return


class TestDataServiceClass(TestCase):
    """
    Test the functionality of the DataService class via the TestDataService.
    """
    def test_query_service(self):
        new_test_query = TestDataService()
        self.assertEqual(new_test_query.query_results, {})
        new_test_query.query_service('mytarget')
        self.assertEqual(new_test_query.query_results, test_query_results)

    def test_to_target(self):
        new_test_query = TestDataService()
        # Show to_target() returns error with no query_results
        with self.assertRaises(MissingDataException):
            new_test_query.to_target()
        # Show to_target() works with the default query_results
        new_test_query.query_targets('mytarget')
        target = new_test_query.to_target()
        self.assertEqual(target.name, test_query_results['name'])
        # Show to_target() works independently of the query.
        new_test_query_results = test_query_results.copy()
        new_test_query_results['name'] = 'target2'
        target2 = new_test_query.to_target(new_test_query_results)
        self.assertEqual(target2.name, 'target2')


class TestUnimplementedDataServiceClass(TestCase):
    """
    Test the functionality of a DataService with unimplemented methods.
    """

    def test_no_create_data_product_from_query(self):
        new_test_query = EmptyTestDataService()
        # Show to_data_product() returns error when create_data_product_from_query undefined
        with self.assertRaises(NotImplementedError):
            new_test_query.to_data_product(test_query_results)

    def test_no_create_target_from_query(self):
        new_test_query = EmptyTestDataService()
        # Show to_data_product() returns error when create_data_product_from_query undefined
        with self.assertRaises(NotImplementedError):
            new_test_query.to_target(test_query_results)

    def test_no_create_reduced_datums_from_query(self):
        new_test_query = EmptyTestDataService()
        # Show to_data_product() returns error when create_data_product_from_query undefined
        with self.assertRaises(NotImplementedError):
            new_test_query.to_reduced_datums(test_query_results)
