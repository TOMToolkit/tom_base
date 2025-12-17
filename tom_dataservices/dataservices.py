from abc import ABC, abstractmethod
import logging

from django.conf import settings
from django.apps import apps
from django.utils.module_loading import import_string

logger = logging.getLogger(__name__)


def get_data_service_classes():
    """
    Imports the Dataservice class from relevant apps and generates a list of data service names.

    Each dataservice class should be contained in a list of dictionaries in an app's apps.py `dataservices` method.
    Each dataservice dictionary should contain a 'class' key with the dot separated path to the dataservice class
    (typically an extension of BaseDataService).

    FOR EXAMPLE:
    [{'class': 'path.to.dataservice.class'}]
    """
    data_service_choices = {}
    for app in apps.get_app_configs():
        try:
            data_services = app.data_services()
        except AttributeError:
            continue
        if data_services:
            for data_service in data_services:
                try:
                    clazz = import_string(data_service['class'])
                except ImportError as e:
                    logger.warning(f'WARNING: Could not import data service class for {app.name} from '
                                   f'{data_service["class"]}.\n'
                                   f'{e}')
                    continue
                data_service_choices[clazz.name] = clazz

    return data_service_choices


def get_data_service_class(name):
    """
    Gets the specific dataservice class for a given dataservice name.

    :returns: Broker class
    :rtype: class
    """
    available_classes = get_data_service_classes()
    try:
        return available_classes[name]
    except KeyError:
        raise ImportError(
            f'''Could not a find a data Service with named {name}.
            Did you install the app?'''
        )


class MissingDataException(Exception):
    pass


class NotConfiguredError(Exception):
    pass


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
    # Base url for the DataService
    base_url = None
    # Notes or limitations on using the DataService
    service_notes = None
    # The path to a specialized table partial for displaying query results
    query_results_table = None

    def __init__(self, query_parameters=None, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Instance variable that can store target query results if necessary
        self.target_results = {}
        # Instance variable that can store query results if necessary
        self.query_results = {}
        # Instance variable that can store query parameters if necessary
        self.query_parameters = query_parameters or {}

    @abstractmethod
    def query_service(self, query_parameters, **kwargs):
        """Takes in the serialized data from the query form and actually submits the query to the service"""

    def pre_query_validation(self, query_parameters):
        """Same thing as query_service, but a dry run"""
        raise NotImplementedError

    def build_query_parameters(self, parameters, **kwargs):
        """Builds the query parameters from the form data"""
        raise NotImplementedError

    def build_headers(self, *args, **kwargs):
        """Builds the headers for the query"""
        return {}

    @classmethod
    def get_form_class(cls):
        """Returns the full form class for querying this service"""
        raise NotImplementedError(f"No Form Class for {cls.name} Data Service")

    @classmethod
    def configuration(cls) -> dict:
        """Returns the configuration dictionary for this service"""
        try:
            return settings.DATA_SERVICES[cls.name]
        except AttributeError as e:
            raise NotConfiguredError(e)
        except KeyError as e:
            raise NotConfiguredError(
                f"""The {e} DataService is not configured.
                    </br>
                    Please see the <a href="{cls.info_url}" target="_blank">documentation</a> for more information.
                """
            )

    @classmethod
    def get_configuration(cls, config_type=None, value=None, **kwargs):
        """
        Syntax: get_configuration([config_type], [value])
        Parameters:
            config_type: The type of configuration to return. If None, returns all configurations.
            value: The default value to return if configuration not found.
        Returns:
            A list of available configurations, or a requested configuration, or if not found the default value.
        """
        data_service_config = cls.configuration()
        if config_type:
            return data_service_config.get(config_type, value)
        return [*data_service_config]

    @classmethod
    def get_credentials(cls, **kwargs):
        """Returns the credentials for this service. Checks the configuration for an api_key by default."""
        return cls.get_configuration('api_key')

    @classmethod
    def urls(cls, **kwargs) -> dict:
        """Dictionary of URLS for the DataService"""
        return {'base_url': cls.base_url, 'info_url': cls.info_url}

    @classmethod
    def get_urls(cls, url_type=None, value=None, **kwargs):
        """
        Syntax: get_urls([url_type], [value])
        Parameters:
            url_type: The type of URL to return. If None, returns all available url types.
            value: The default value to return if the requested url is not found.
        Returns:
            A list of available uls, or a requested url, or if not found, the default value.
        """
        urls = cls.urls()
        if url_type:
            return urls.get(url_type, value)
        return [*urls]

    def get_additional_context_data(self):
        """
        Called by the View.get_context_data() and adds DataService context to the View’s context dictionary
        """
        return {}

    def get_success_message(self, **kwargs):
        """Returns a success message to display in the UI after making the query."""
        return "Query completed successfully."

    def get_simple_form_partial(self):
        """Returns a path to a simplified bare-minimum partial form that can be used to access the DataService."""
        return None

    def get_advanced_form_partial(self):
        """Returns a path to a full or advanced partial form that can be used to access the DataService."""
        return None

    def query_forced_photometry(self, query_parameters, **kwargs):
        """Set up and run a specialized query for a DataService’s forced photometry service."""
        return self.query_service(query_parameters, **kwargs)

    def query_photometry(self, query_parameters, **kwargs):
        """Set up and run a specialized query for a DataService’s photometry service."""
        return self.query_service(query_parameters, **kwargs)

    def query_spectroscopy(self, query_parameters, **kwargs):
        """Set up and run a specialized query for a DataService’s spectroscopy service."""
        return self.query_service(query_parameters, **kwargs)

    def query_aliases(self, query_parameters, **kwargs):
        """Set up and run a specialized query for retrieving alternate names from a DataService."""
        return self.query_service(query_parameters, **kwargs)

    def query_targets(self, query_parameters, **kwargs):
        """Set up and run a specialized query for retrieving targets from a DataService."""
        return self.query_service(query_parameters, **kwargs)

    def to_data_product(self, query_results=None, **kwargs):
        """
        Upper level function to create a new DataProduct from the query results
        Can take either new query results, or use stored results form a recent `query_service()`
        :param query_results: Query results from the DataService
        :returns: DataProduct object
        """
        query_results = query_results or self.query_results
        if not query_results:
            raise MissingDataException('No query results. Did you call query_service()?')
        else:
            return self.create_data_product_from_query(query_results, **kwargs)

    def create_data_product_from_query(self, query_results=None, **kwargs):
        """Create a new DataProduct from the query results"""
        raise NotImplementedError

    def to_reduced_datums(self, target, query_results=None, **kwargs):
        """
        Upper level function to create a new ReducedDatum from the query results
        Can take either new query results, or use stored results form a recent `query_service()`
        :param target: Target object to associate with the ReducedDatum
        :param query_results: Query results from the DataService
        :returns: ReducedDatum object
        """
        query_results = query_results or self.query_results
        if not query_results:
            raise MissingDataException('No query results. Did you call query_service()?')
        else:
            return self.create_reduced_datums_from_query(target, query_results, **kwargs)

    def create_reduced_datums_from_query(self, target, query_results=None, **kwargs):
        """Create a new reduced_datum of the appropriate type from the query results"""
        raise NotImplementedError

    def to_target(self, target_results=None, **kwargs):
        """
        Upper level function to create a new target from the query results
        Can take either new query results, or use stored results form a recent `query_service()`
        :param query_results: Query results from the DataService
        :returns: Target object, dictionary of target_extras, and list of aliases
        """
        target_parameters = target_results or self.target_results
        if not target_parameters:
            raise MissingDataException('No query results. Did you call query_service()?')
        else:
            target = self.create_target_from_query(target_parameters, **kwargs)
            extras = self.create_target_extras_from_query(target_parameters, **kwargs)
            aliases = self.create_aliases_from_query(target_parameters, **kwargs)
            return target, extras, aliases

    def create_target_from_query(self, target_result, **kwargs):
        """Create a new target from a single instance of the target results.
        :param target_result: dictionary describing target details based on query result
        :returns: target object
        :rtype: `Target`
        """
        raise NotImplementedError

    def create_target_extras_from_query(self, query_results, **kwargs):
        """Create a new target from the query results
        :returns: dict of extras to be added to a new Target
        :rtype: `dict`
        """
        return {}

    def create_aliases_from_query(self, query_results, **kwargs):
        """Create a new target from the query results
        :returns: list of aliases to be added to a new Target
        :rtype: `list`
        """
        return []
