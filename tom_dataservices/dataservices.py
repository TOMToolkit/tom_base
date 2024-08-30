from abc import ABC, abstractmethod


class BaseDataService(ABC):
    """
    Base class for all Data Services. Data Services are classes that are responsible for querying external services
    """
    name = 'BaseDataService'
    verbose_name = name
    info_url = None
    service_notes = None
    query_results = {}

    @abstractmethod
    def validate_form(self, query_parameters):
        """Same thing as query_service, but a dry run"""
        pass

    @abstractmethod
    def query_service(self, query_parameters):
        """takes in the serialized data from the query form and actually submits the query to the service"""
        pass

    @abstractmethod
    def get_form(self):
        """Returns the form for querying this service"""
        pass

    def get_context_data(self):
        """
        Called by the View.get_context_data() and adds DataService context to the View’s context dictionary
        """
        pass

    def get_success_message(self):
        """Returns a success message to display in the UI after making the query."""
        pass

    def get_simple_form(self):
        """Returns a simplified bare-minimum form that can be used to access the DataService."""
        pass

    def get_forced_photometry(self):
        """Query a DataService’s forced photometry service"""
        pass

    def to_data_product(self):
        """Create a new DataProduct from the query results"""
        pass

    def to_reduced_datums(self, query_results):
        """Create a new ReducedDatum of the appropriate type from the query results"""
        pass

    def to_target(self, query_results):
        """Create a new target from the query results"""
        pass
