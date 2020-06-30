from abc import ABC, abstractmethod
from importlib import import_module
import copy
import json
import logging
import requests

from crispy_forms.helper import FormHelper
from crispy_forms.layout import ButtonHolder, Layout, Submit, Div, HTML
from django import forms
from django.conf import settings
from django.contrib.auth.models import Group
from django.core.files.base import ContentFile

from tom_targets.models import Target

logger = logging.getLogger(__name__)

DEFAULT_FACILITY_CLASSES = [
        'tom_observations.facilities.lco.LCOFacility',
        'tom_observations.facilities.gemini.GEMFacility',
        'tom_observations.facilities.soar.SOARFacility',
        'tom_observations.facilities.lt.LTFacility'
]

try:
    AUTO_THUMBNAILS = settings.AUTO_THUMBNAILS
except AttributeError:
    AUTO_THUMBNAILS = False


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


# TODO: Ensure docstrings are up to date


class BaseObservationForm(forms.Form):
    """
    This is the class that is responsible for displaying the observation request form.
    This form is meant to be subclassed by more specific BaseForm classes that represent a
    form for a particular type of facility. For implementing your own form, please look to
    the other BaseObservationForms.

    For an implementation example please see
    https://github.com/TOMToolkit/tom_base/blob/master/tom_observations/facilities/lco.py#L132
    """
    facility = forms.CharField(required=True, max_length=50, widget=forms.HiddenInput())
    target_id = forms.IntegerField(required=True, widget=forms.HiddenInput())
    observation_type = forms.CharField(required=False, max_length=50, widget=forms.HiddenInput())

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.helper = FormHelper()
        if settings.TARGET_PERMISSIONS_ONLY:
            self.common_layout = Layout('facility', 'target_id', 'observation_type')
        else:
            self.fields['groups'] = forms.ModelMultipleChoiceField(Group.objects.none(),
                                                                   required=False,
                                                                   widget=forms.CheckboxSelectMultiple)
            self.common_layout = Layout('facility', 'target_id', 'observation_type', 'groups')
        self.helper.layout = Layout(
            self.common_layout,
            self.layout(),
            self.button_layout()
        )

    def layout(self):
        return

    def button_layout(self):
        target_id = self.initial.get('target_id')
        return ButtonHolder(
                Submit('submit', 'Submit'),
                HTML(f'''<a class="btn btn-outline-primary" href={{% url 'tom_targets:detail' {target_id} %}}>
                         Back</a>''')
            )

    def is_valid(self):
        # TODO: Make this call the validate_observation method in facility
        return super().is_valid()

    def serialize_parameters(self):
        parameters = copy.deepcopy(self.cleaned_data)
        parameters.pop('groups', None)
        return json.dumps(parameters)

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


class BaseRoboticObservationForm(BaseObservationForm):
    """
    This is the class that is responsible for displaying the observation request form.
    Facility classes that provide a form should subclass this form. It provides
    some base shared functionality. Extra fields are provided below.
    The layout is handled by Django crispy forms which allows customizability of the
    form layout without needing to write html templates:
    https://django-crispy-forms.readthedocs.io/en/d-0/layouts.html
    See the documentation on Django forms for more information.

    This specific class is intended for use with robotic facilities, such as LCO, Gemini, and SOAR.

    For an implementation example please see
    https://github.com/TOMToolkit/tom_base/blob/master/tom_observations/facilities/lco.py#L132
    """
    pass


# This aliasing exists to support backwards compatibility
GenericObservationForm = BaseRoboticObservationForm


class BaseManualObservationForm(BaseObservationForm):
    """
    This is the class that is responsible for displaying the observation request form.
    Facility classes that provide a form should subclass this form. It provides
    some base shared functionality. Extra fields are provided below.
    The layout is handled by Django crispy forms which allows customizability of the
    form layout without needing to write html templates:
    https://django-crispy-forms.readthedocs.io/en/d-0/layouts.html
    See the documentation on Django forms for more information.

    This specific class is intended for use with classical-style manual facilities.

    For an implementation example please see
    https://github.com/TOMToolkit/tom_base/blob/master/tom_observations/facilities/lco.py#L132
    """
    name = forms.CharField()
    start = forms.CharField(widget=forms.TextInput(attrs={'type': 'date'}))
    end = forms.CharField(required=False, widget=forms.TextInput(attrs={'type': 'date'}))
    observation_id = forms.CharField(required=False)
    observation_params = forms.CharField(required=False, widget=forms.Textarea(attrs={'type': 'json'}))

    def layout(self):
        return Div(
            Div('name', 'observation_id'),
            Div(
                Div('start', css_class='col'),
                Div('end', css_class='col'),
                css_class='form-row'
            ),
            Div('observation_params')
        )


class BaseObservationFacility(ABC):
    """
    This is the class that is responsible for defining the base facility class.
    This form is meant to be subclassed by more specific BaseFacility classes that represent a
    form for a particular type of facility. For implementing your own form, please look to
    the other BaseObservationFacilities.
    """
    name = 'BaseObservation'

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

        # Add any JPEG images created from DataProducts
        image_products = DataProduct.objects.filter(
            observation_record_id=observation_record.id, data_product_type='image_file'
        )
        for product in image_products:
            products['saved'].append(product)
        return products

    @abstractmethod
    def get_form(self, observation_type):
        """
        This method takes in an observation type and returns the form type that matches it.
        """
        pass

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

    def get_flux_constant(self):
        """
        Returns the astropy quantity that a facility uses for its spectral flux conversion.
        """
        pass

    def get_wavelength_units(self):
        """
        Returns the astropy units that a facility uses for its spectral wavelengths
        """
        pass

    def is_fits_facility(self, header):
        """
        Returns True if the FITS header is from this facility based on valid keywords and associated
        values, False otherwise.
        """
        return False

    def get_start_end_keywords(self):
        """
        Returns the keywords representing the start and end of an observation window for a facility. Defaults to
        ``start`` and ``end``.
        """
        return 'start', 'end'

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
        Return an iterable of dictionaries that contain the information
        necessary to be used in the planning (visibility) tool. The
        iterable should contain dictionaries each that contain sitecode,
        latitude, longitude and elevation. This is the static information
        about a site.
        """
        pass

    def get_facility_weather_urls(self):
        """
        Returns a dictionary containing a URL for weather information
        for each site in the Facility SITES. This is intended to be useful
        in observation planning.

        `facility_weather = {'code': 'XYZ', 'sites': [ site_dict, ... ]}`
        where
        `site_dict = {'code': 'XYZ', 'weather_url': 'http://path/to/weather'}`

        """
        return {}

    def get_facility_status(self):
        """
        Returns a dictionary describing the current availability of the Facility
        telescopes. This is intended to be useful in observation planning.
        The top-level (Facility) dictionary has a list of sites. Each site
        is represented by a site dictionary which has a list of telescopes.
        Each telescope has an identifier (code) and an status string.

        The dictionary hierarchy is of the form:

        `facility_dict = {'code': 'XYZ', 'sites': [ site_dict, ... ]}`
        where
        `site_dict = {'code': 'XYZ', 'telescopes': [ telescope_dict, ... ]}`
        where
        `telescope_dict = {'code': 'XYZ', 'status': 'AVAILABILITY'}`

        See lco.py for a concrete implementation example.
        """
        return {}

    @abstractmethod
    def get_observation_url(self, observation_id):
        """
        Takes an observation id and return the url for which a user
        can view the observation at an external location. In this case,
        we return a URL to the LCO observation portal's observation
        record page.
        """
        pass


class BaseRoboticObservationFacility(BaseObservationFacility):
    """
    The facility class contains all the logic specific to the facility it is
    written for. Some methods are used only internally (starting with an
    underscore) but some need to be implemented by all facility classes.
    All facilities should inherit from  this class which
    provides some base functionality.
    In order to make use of a facility class, add the path to
    ``TOM_FACILITY_CLASSES`` in your ``settings.py``.

    This specific class is intended for use with robotic facilities, such as LCO, Gemini, and SOAR.

    For an implementation example, please see
    https://github.com/TOMToolkit/tom_base/blob/master/tom_observations/facilities/lco.py
    """
    name = 'BaseRobotic'  # rename in concrete subclasses

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

    def save_data_products(self, observation_record, product_id=None):
        from tom_dataproducts.models import DataProduct
        from tom_dataproducts.utils import create_image_dataproduct
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
                logger.info('Saved new dataproduct: {}'.format(dp.data))
            if AUTO_THUMBNAILS:
                create_image_dataproduct(dp)
                dp.get_preview()
            final_products.append(dp)
        return final_products

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


# This aliasing exists to support backwards compatibility
GenericObservationFacility = BaseRoboticObservationFacility


class BaseManualObservationFacility(BaseObservationFacility):
    """
    The facility class contains all the logic specific to the facility it is
    written for. Some methods are used only internally (starting with an
    underscore) but some need to be implemented by all facility classes.
    All facilities should inherit from  this class which
    provides some base functionality.
    In order to make use of a facility class, add the path to
    ``TOM_FACILITY_CLASSES`` in your ``settings.py``.

    This specific class is intended for use with classical-style manual facilities.

    TODO: Add an implementation example.
    """
    name = 'BaseManual'  # rename in concrete subclasses
