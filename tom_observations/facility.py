from django.conf import settings
from django import forms
from importlib import import_module
from crispy_forms.helper import FormHelper
from crispy_forms.layout import Submit, Layout
from django.core.files.base import ContentFile
from abc import ABC, abstractmethod
import requests
import json

from tom_targets.models import Target


DEFAULT_FACILITY_CLASSES = [
        'tom_observations.facilities.lco.LCOFacility',
        'tom_observations.facilities.gemini.GEMFacility',
]


def get_service_classes():
    try:
        TOM_FACILITY_CLASSES = settings.TOM_FACILITY_CLASSES
    except AttributeError:
        TOM_FACILITY_CLASSES = DEFAULT_FACILITY_CLASSES

    service_choices = {}
    for service in TOM_FACILITY_CLASSES:
        mod_name, class_name = service.rsplit('.', 1)
        try:
            mod = import_module(mod_name)
            clazz = getattr(mod, class_name)
        except (ImportError, AttributeError):
            raise ImportError('Could not import {}. Did you provide the correct path?'.format(service))
        service_choices[clazz.name] = clazz
    return service_choices


def get_service_class(name):
    available_classes = get_service_classes()
    try:
        return available_classes[name]
    except KeyError:
        raise ImportError('Could not a find a facility with that name. Did you add it to TOM_FACILITY_CLASSES?')


class GenericObservationFacility(ABC):
    """
    The facility class contains all the logic specific to the facility it is
    written for. Some methods are used only internally (starting with an
    underscore) but some need to be implemented by all facility classes.
    All facilities should inherit from  this class which
    provides some base functionality.
    In order to make use of a facility class, add the path to
    TOM_FACILITY_CLASSES in your settings.py.

    For an implementation example please see
    https://github.com/TOMToolkit/tom_base/blob/master/tom_observations/facilities/lco.py
    """

    def update_observation_status(self, observation_id):
        from tom_observations.models import ObservationRecord
        try:
            record = ObservationRecord.objects.get(observation_id=observation_id)
            status = self.get_observation_status(observation_id)
            record.status = status['state']
            record.scheduled_start = status['scheduled_start']
            record.scheduled_end = status['scheduled_end']
            record.save()
        except ObservationRecord.DoesNotExist:
            raise Exception('No record exists for that observation id')

    def update_all_observation_statuses(self, target=None):
        from tom_observations.models import ObservationRecord
        failed_records = []
        records = ObservationRecord.objects.filter(facility=self.name)
        if target:
            records = records.filter(target=target)
        records = records.exclude(status__in=self.get_terminal_observing_states())
        for record in records:
            try:
                self.update_observation_status(record.observation_id)
            except Exception as e:
                failed_records.append((record.observation_id, str(e)))
        return failed_records

    def all_data_products(self, observation_record):
        from tom_dataproducts.models import DataProduct
        products = {'saved': [], 'unsaved': []}
        for product in self.data_products(observation_record.observation_id):
            try:
                dp = DataProduct.objects.get(product_id=product['id'])
                products['saved'].append(dp)
            except DataProduct.DoesNotExist:
                products['unsaved'].append(product)
        # Obtain products uploaded manually by users
        user_products = DataProduct.objects.filter(
            observation_record_id=observation_record.id, product_id=None
        )
        for product in user_products:
            products['saved'].append(product)
        return products

    def save_data_products(self, observation_record, product_id=None):
        from tom_dataproducts.models import DataProduct
        final_products = []
        products = self.data_products(observation_record.observation_id, product_id)

        for product in products:
            dp, created = DataProduct.objects.get_or_create(
                product_id=product['id'],
                target=observation_record.target,
                observation_record=observation_record,
            )
            if created:
                product_data = requests.get(product['url']).content
                dfile = ContentFile(product_data)
                dp.data.save(product['filename'], dfile)
                dp.save()
            final_products.append(dp)
        return final_products

    @abstractmethod
    def submit_observation(self, observation_payload):
        """
        This method takes in the serialized data from the form and actually
        submits the observation to the remote api
        """
        pass

    @abstractmethod
    def validate_observation(self, observation_payload):
        """
        Same thing as submit_observation, but a dry run. You can
        skip this in different modules by just using "pass"
        """
        pass

    @abstractmethod
    def get_observation_url(self, observation_id):
        """
        Takes an observation id and return the url for which a user
        can view the observation at an external location. In this case,
        we return a URL to the LCO observation portal's observation
        record page.
        """
        pass

    @abstractmethod
    def get_terminal_observing_states(self):
        """
        Returns the states for which an observation is not expected
        to change.
        """
        pass

    @abstractmethod
    def get_observing_sites(self):
        """
        Return a list of dictionaries that contain the information
        necessary to be used in the planning (visibility) tool. The
        list should contain dictionaries each that contain sitecode,
        latitude, longitude and elevation.
        """
        pass

    @abstractmethod
    def get_observation_status(self, observation_id):
        """
        Return the status for a single observation. observation_id should
        be able to be used to retrieve the status from the external service.
        """
        pass

    @abstractmethod
    def data_products(self, observation_id, product_id=None):
        """
        Using an observation_id, retrieve a list of the data
        products that belong to this observation. In this case,
        the LCO module retrieves a list of frames from the LCO
        data archive.
        """
        pass


class GenericObservationForm(forms.Form):
    """
    This is the class that is responsible for displaying the observation request form.
    Facility classes that provide a form should subclass this form. It provides
    some base shared functionality. Extra fields are provided below.
    The layout is handled by Django crispy forms which allows customizability of the
    form layout without needing to write html templates:
    https://django-crispy-forms.readthedocs.io/en/d-0/layouts.html
    See the documentation on Django forms for more information.

    For an implementation example please see
    https://github.com/TOMToolkit/tom_base/blob/master/tom_observations/facilities/lco.py#L132
    """
    facility = forms.CharField(required=True, max_length=50, widget=forms.HiddenInput())
    target_id = forms.IntegerField(required=True, widget=forms.HiddenInput())

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.helper = FormHelper()
        self.helper.add_input(Submit('submit', 'Submit'))
        self.common_layout = Layout('facility', 'target_id')

    def serialize_parameters(self):
        return json.dumps(self.cleaned_data)

    @property
    def observation_payload(self):
        """
        This method is called to extract the data from the form into a dictionary that
        can be used by the rest of the module. In the base implementation it simply dumps
        the form into a json string.
        """
        target = Target.objects.get(pk=self.cleaned_data['target_id'])
        return {
            'target_id': target.id,
            'params': self.serialize_parameters()
        }
