from abc import ABC, abstractmethod
import logging

from crispy_forms.helper import FormHelper
from crispy_forms.layout import ButtonHolder, Layout, Submit
from django import forms
from django.conf import settings
from django.utils.module_loading import import_string

logger = logging.getLogger(__name__)


def get_service_classes():
    try:
        forced_photometry_services = settings.FORCED_PHOTOMETRY_SERVICES
    except AttributeError:
        return {}

    service_choices = {}
    for service in forced_photometry_services.values():
        try:
            clazz = import_string(service.get('class'))
        except (ImportError, AttributeError):
            raise ImportError(f'Could not import {service}. Did you provide the correct path?')
        service_choices[clazz.name] = clazz
    return service_choices


def get_service_class(name):
    available_classes = get_service_classes()
    try:
        return available_classes[name]
    except KeyError:
        raise ImportError((
            f'Could not a find a forced photometry service with the name {name}. '
            'Did you add it to TOM_FORCED_PHOTOMETRY_CLASSES?'))


class ForcedPhotometryServiceException(Exception):
    pass


class BaseForcedPhotometryQueryForm(forms.Form):
    """
    This is the class that is responsible for displaying the forced photometry request form.
    This form is meant to be subclassed by more specific classes that represent a
    form for a specific forced photometry service, including the query parameters it supports.

    For an implementation example please see
    https://github.com/TOMToolkit/tom_base/blob/main/tom_dataproducts/forced_photometry/atlas.py
    """
    service = forms.CharField(required=True, max_length=50, widget=forms.HiddenInput())
    target_id = forms.IntegerField(required=True, widget=forms.HiddenInput())

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.helper = FormHelper()
        self.common_layout = Layout('service', 'target_id')
        self.helper.layout = Layout(
            self.common_layout,
            self.layout(),
            self.button_layout()
        )

    def layout(self):
        return

    def button_layout(self):
        return ButtonHolder(
            Submit('submit', 'Submit'),
        )


class BaseForcedPhotometryService(ABC):
    """
    This is the class that is responsible for defining the base forced photometry service class.
    This form is meant to be subclassed by more specific classes that represent a
    form for a particular forced photometry service.
    """
    name = 'BaseForcedPhotometryService'

    @abstractmethod
    def get_form(self):
        """
        This method returns the form for querying this service.
        """

    @abstractmethod
    def query_service(self, query_parameters):
        """
        This method takes in the serialized data from the query form and actually
        submits the query to the service
        """

    @abstractmethod
    def validate_form(self, query_parameters):
        """
        Same thing as query_service, but a dry run. You can
        skip this in different modules by just using "pass"

        Typically called by the .is_valid() method.
        """

    @abstractmethod
    def get_success_message(self):
        """
        This should return a message that shows up in the UI after making the query.
        It should explain what is happening / next steps, i.e. if the results will be
        emailed to you it should say that and that you must upload them once received.
        """

    @abstractmethod
    def get_data_product_type(self):
        """
        This should return the data_product_type for data products produced by this service
        Make sure to also add this type in your settings to DATA_PRODUCT_TYPES and
        DATA_PROCESSORS.
        """
