import ephem
from tom_observations.facility import GenericObservationFacility
from tom_observations.models import ObservationRecord

# Site data matches built-in pyephem observer data for Los Angeles
SITES = {
    'Los Angeles': {
        'latitude': 34.052222,
        'longitude': -117.756306,
        'elevation': 86.847092
    }
}


class FakeFacility(GenericObservationFacility):
    name = 'Fake Facility'

    @classmethod
    def get_observing_sites(clz):
        return SITES

    @classmethod
    def get_observation_url(clzz, observation_id):
        return ''

    @classmethod
    def observation_records(clz):
        return ObservationRecord.objects.all()

    @classmethod
    def data_products(clz, observation_record, request=None):
        return {'saved': []}

    @classmethod
    def get_observation_status(clz, observation_id):
        return 'COMPLETED'

    @classmethod
    def get_terminal_observing_states(clz):
        return ['COMPLETED', 'FAILED']
