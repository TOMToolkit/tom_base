from abc import abstractmethod
import logging
import requests

from django.core.files.base import ContentFile

from tom_observations.facility import GenericObservationFacility, AUTO_THUMBNAILS

logger = logging.getLogger(__name__)


class GenericManualFacility(GenericObservationFacility):
    """
    The facility class contains all the logic specific to the facility it is
    written for. Some methods are used only internally (starting with an
    underscore) but some need to be implemented by all facility classes.
    All facilities should inherit from  this class which
    provides some base functionality.
    In order to make use of a facility class, add the path to
    ``TOM_FACILITY_CLASSES`` in your ``settings.py``.

    For an implementation example, please see
    https://github.com/TOMToolkit/tom_base/blob/master/tom_observations/facilities/lco.py
    """

    name = 'MAN'
    observation_types = [('IMAGING', 'Imaging'), ('SPECTRA', 'Spectroscopy')]
    SITES = {}

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

        # Add any JPEG images created from DataProducts
        image_products = DataProduct.objects.filter(
            observation_record_id=observation_record.id, data_product_type='image_file'
        )
        for product in image_products:
            products['saved'].append(product)
        return products

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

    @abstractmethod
    def get_observation_url(self, observation_id):
        """
        Takes an observation id and return the url for which a user
        can view the observation at an external location. In this case,
        we return a URL to the LCO observation portal's observation
        record page.
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
