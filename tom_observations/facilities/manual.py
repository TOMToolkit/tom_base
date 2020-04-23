import logging

from django.conf import settings

from tom_observations.facility import BaseManualObservationFacility, BaseManualObservationForm

logger = logging.getLogger(__name__)


#
# facility properties needed by both the Facility and Form classes
# are candidates for module-level definitions. If the property is just
# for the Facility, put it in the class definition
#

try:
    ZZZ_SETTINGS = settings.FACILITIES['ZZZ']
except KeyError:
    ZZZ_SETTINGS = {
    }

ZZZ_SITES = {
    'Zero-zero Island': {
        'sitecode': 'zzz',  # top-secret observing site on Zero-zero Island
        'latitude': 0.0,
        'longitude': 0.0,
        'elevation': 0.0
    },
}
ZZZ_TERMINAL_OBSERVING_STATES = ['Completed']


class TestManualFacility(BaseManualObservationFacility):
    """
    """

    name = 'ZZZ'
    observation_types = [('IMAGING', 'Imaging')]

    def get_form(self, observation_type):
        """
        This method takes in an observation type and returns the form type that matches it.
        """
        return BaseManualObservationForm

    def submit_observation(self, observation_payload):
        """
        This method takes in the serialized data from the form.

        """
        # TODO: finish implementation
        print(f'observation_payload: {observation_payload}')
        obs_ids = []
        for payload in observation_payload:
            obs_ids.append(f'{payload}')

        return obs_ids

    def validate_observation(self, observation_payload):
        """
        Same thing as submit_observation, but a dry run. You can
        skip this in different modules by just using "pass"
        """
        # TODO: implement me
        raise NotImplementedError

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

    def get_terminal_observing_states(self):
        """
        Returns the states for which an observation is not expected
        to change.
        """
        return ZZZ_TERMINAL_OBSERVING_STATES

    def get_observation_url(self, observation_id):
        return

    def get_observing_sites(self):
        """
        Return a list of dictionaries that contain the information
        necessary to be used in the planning (visibility) tool. The
        list should contain dictionaries each that contain sitecode,
        latitude, longitude and elevation.
        """
        return ZZZ_SITES

    def get_observation_status(self, observation_id):
        """
        Return the status for a single observation. observation_id should
        be able to be used to retrieve the status from the external service.
        """
        # TODO: implement me
        raise NotImplementedError

    def data_products(self, observation_id, product_id=None):
        """
        Using an observation_id, retrieve a list of the data
        products that belong to this observation. In this case,
        the LCO module retrieves a list of frames from the LCO
        data archive.
        """
        return []
