from abc import ABC, abstractmethod
import logging
from typing import List, Tuple

from django.conf import settings
from django.apps import apps
from django.utils.module_loading import import_string

from tom_targets.models import TargetName

logger = logging.getLogger(__name__)


def get_data_service_classes():
    """
    Imports the Dataservice class from relevant apps and generates a list of data service names.

    Each dataservice class should be contained in a list of dictionaries in an app's apps.py `dataservices` method.
    Each dataservice dictionary should contain a 'class' key with the dot separated path to the dataservice class
    (typically an extension of DataService).

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


class QueryServiceError(Exception):
    """
    Represents a higher level error when an underlying service or client library fails.
    """
    pass


class DataService(ABC):
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
    # App Version
    app_version = None
    # Link to app github repo
    app_link = None

    def __init__(self, query_parameters=None, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Instance variable that can store target query results if necessary
        self.target_results = {}
        # Instance variable that can store photometry query results if necessary
        self.photometry_results = {}
        # Instance variable that can store query results if necessary
        self.query_results = {}
        # Instance variable that can store query parameters if necessary
        self.query_parameters = query_parameters or {}

    @abstractmethod
    def query_service(self, query_parameters, **kwargs):
        """Takes in the serialized data from the query form and actually submits the query to the service"""

    def pre_query_validation(self, query_parameters):
        """Same thing as query_service, but a dry run"""
        raise NotImplementedError(f'pre_query_validation method has not been implemented for {self.name}')

    def build_query_parameters(self, parameters, **kwargs):
        """Builds the query parameters from the form data"""
        raise NotImplementedError(f'build_query_parameters method has not been implemented for {self.name}')

    def build_query_parameters_from_target(self, target, **kwargs):
        raise NotImplementedError('build_query_parameters_from_target method has not been implemented' +
                                  f'for {self.name}.'
                                  )

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
        Get all of the configuration or specific configuration values associated with this dataservice.

        :Syntax: get_configuration([config_type], [value])
        :param config_type: The type of configuration to return. If None, returns all configurations.
        :param value: The default value to return if configuration not found.
        :return: A list of available configurations, or a requested configuration, or if not found, the default value.
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
        Get all urls or a specific url associated with the dataservice.

        :Syntax: get_urls([url_type], [value])
        :param url_type: The type of URL to return. If None, returns all available url types.
        :param value: The default value to return if the requested url is not found.
        :return: A list of available uls, or a requested url, or if not found, the default value.
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
        raise NotImplementedError(f'query_forced_photometry method has not been implemented for {self.name}')

    def query_photometry(self, query_parameters, **kwargs):
        """Set up and run a specialized query for a DataService’s photometry service."""
        raise NotImplementedError(f'query_photometry method has not been implemented for {self.name}')

    def query_spectroscopy(self, query_parameters, **kwargs):
        """Set up and run a specialized query for a DataService’s spectroscopy service."""
        raise NotImplementedError(f'query_spectroscopy method has not been implemented for {self.name}')

    def query_reduced_data(self, target, **kwargs):
        """Set up and run a specialized query to retrieve Reduced Datums from a Data Service"""
        query_parameters = self.build_query_parameters_from_target(target)
        try:
            phot_results = self.query_photometry(query_parameters, **kwargs)
        except NotImplementedError:
            phot_results = []
        try:
            spec_results = self.query_spectroscopy(query_parameters, **kwargs)
        except NotImplementedError:
            spec_results = []
        try:
            forced_phot_results = self.query_forced_photometry(query_parameters, **kwargs)
        except NotImplementedError:
            forced_phot_results = []
        return {'photometry': phot_results,
                'spectroscopy': spec_results,
                'forced_photometry': forced_phot_results}

    def query_aliases(self, query_parameters, **kwargs) -> List:
        """
        Set up and run a specialized query for retrieving target names from a DataService.
        This method will usually call `query_service()` and translate the results from the dataservice into a
        list of target names.

        :param query_parameters: This is the output from build_query_parameters()
        :return: A list of target names
        :rtype: List
        """
        return []

    def query_targets(self, query_parameters, **kwargs) -> List[dict]:
        """
        Set up and run a specialized query for retrieving targets from a DataService.
        This method will usually call `query_service()` and translate the results from the dataservice into a
        list of dictionaries describing the returned targets.

        :param query_parameters: This is the output from build_query_parameters()
        :return: A list of dictionaries describing the resulting targets. Include 'reduced_datums' and/or 'aliases' as
        keys in this dictionary to add associated data and alternate names without perfoming additional queries.
        :rtype: List[dict]
        """
        return [{}]

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
        raise NotImplementedError(f'create_data_product_from_query method has not been implemented for {self.name}')

    def to_reduced_datums(self, target, data_results=None, **kwargs):
        """
        Upper level function to create a new ReducedDatum from the query results
        This method is not intended to be extended. This method passes the output
        of query_reduced_data() to create_reduced_datums_from_query()
        :param target: Target object to associate with the ReducedDatum
        :param data_results: Query results from the DataService storing observation data. This should be a dictionary
            with each key being a data_type (i.e. Photometry, Spectroscopy, etc.)
        """
        if not data_results:
            raise MissingDataException('No Reduced Data dictionary found.')
        for key in data_results.keys():
            print(key)
            self.create_reduced_datums_from_query(target, data_results[key], key, **kwargs)
        return

    def create_reduced_datums_from_query(self, target, data=None, data_type=None, **kwargs) -> List:
        """
        Create and save new reduced_datums of the appropriate data_type from the query results
        Be sure to use `ReducedDatum.objects.get_or_create()` when creating new objects.

        :param target: Target Object to be associated with the reduced data
        :param data: List of data dictionaries of the appropriate `data_type`
        :param data_type: An appropriate data type as listed in tom_dataproducts.models.DATA_TYPE_CHOICES
        :return: List of Reduced datums (either retrieved or created)
        """
        raise NotImplementedError

    def to_target(self, target_result=None, **kwargs) -> Tuple[dict, dict, dict]:
        """
        Upper level function to create a new target from the query results
        This method is not intended to be extended. This method passes a single instance of the output
        of query_targets() to create_target_from_query(), create_target_extras_from_query() and
        create_aliases_from_query().
        Intended usage: Call to_target on each element of the target_data list of dictionaries from query_target.
        (see views.py::CreateTargetFromQueryView)
        :param target_results: Dictionary containing target information.
        :returns: Target object, dictionary of target_extras, and list of aliases
        """
        if not target_result:
            raise MissingDataException('No query results. Did you call query_service()?')
        else:
            target = self.create_target_from_query(target_result, **kwargs)
            extras = self.create_target_extras_from_query(target_result, **kwargs)
            aliases = self.create_aliases_from_query(target_result.get('aliases', []), **kwargs)
            return target, extras, aliases

    def create_target_from_query(self, target_result, **kwargs):
        """Create a new target from a single instance of the target results.
        :param target_result: dictionary describing target details based on query result
        :returns: target object
        :rtype: `Target`
        """
        raise NotImplementedError(f'create_target_from_query method has not been implemented for {self.name}')

    def create_target_extras_from_query(self, query_results, **kwargs):
        """Create a new target from the query results
        :returns: dict of extras to be added to a new Target
        :rtype: `dict`
        """
        return {}

    def create_aliases_from_query(self, alias_results: List, **kwargs) -> List:
        """Create a new target from the query results
        This method should be over ridden with a method that creates a list of TargetName objects:
        `TargetName(name=alias)` that will be saved as part of the `Target.save(extras=extras, names=aliases)` call.
        :param query_result: list of dictionaries describing target details based on query result
        :returns: list of TargetName objects to be added to a new Target
        :rtype: `list`
        """
        aliases = []
        for alias in alias_results:
            aliases.append(TargetName(name=alias))
        return aliases
