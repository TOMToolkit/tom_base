from abc import ABC, abstractmethod


class BaseDataService(ABC):
    """
    Base class for all Data Services. Data Services are classes that are responsible for querying external services
    and returning data.
    """
    # Recognizable name for the DataService (Gaia, TNS, etc)
    name = 'BaseDataService'
    # Full name for the DataService (Hermes Messaging Service, Pan-STARRS1 DR2 Query Service, etc.)
    verbose_name = name
    # Url for more info about the DataService
    info_url = None
    # Notes or limitations on using the DataService
    service_notes = None
    # Class variable that can store query results if necessary
    query_results = {}

    @abstractmethod
    def pre_query_validation_service(self, query_parameters):
        """Same thing as query_service, but a dry run"""

    @abstractmethod
    def query_service(self, query_parameters):
        """takes in the serialized data from the query form and actually submits the query to the service"""

    @abstractmethod
    def get_form_class(self):
        """Returns the full form class for querying this service"""

    def get_additional_context_data(self):
        """
        Called by the View.get_context_data() and adds DataService context to the View’s context dictionary
        """
        return {}

    def get_success_message(self, **kwargs):
        """Returns a success message to display in the UI after making the query."""
        return "Query completed successfully."

    def get_simple_form_class(self):
        """Returns a simplified bare-minimum form that can be used to access the DataService."""
        raise NotImplementedError

    def query_forced_photometry(self, query_parameters):
        """Set up and run a specialized query for a DataService’s forced photometry service."""
        return self.query_service(query_parameters)

    def query_photometry(self, query_parameters):
        """Set up and run a specialized query for a DataService’s photometry service."""
        return self.query_service(query_parameters)

    def query_spectroscopy(self, query_parameters):
        """Set up and run a specialized query for a DataService’s spectroscopy service."""
        return self.query_service(query_parameters)

    def query_aliases(self, query_parameters):
        """Set up and run a specialized query for retrieving alternate names from a DataService."""
        return self.query_service(query_parameters)

    def query_targets(self, query_parameters):
        """Set up and run a specialized query for retrieving targets from a DataService."""
        return self.query_service(query_parameters)

    def to_data_product(self, query_results):
        """Create a new DataProduct from the query results"""
        raise NotImplementedError

    def to_reduced_datums(self, query_results):
        """Create a new ReducedDatum of the appropriate type from the query results"""
        raise NotImplementedError

    def to_target(self, query_results):
        """Create a new target from the query results"""
        raise NotImplementedError
