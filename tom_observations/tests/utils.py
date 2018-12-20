from django import forms

from tom_observations.facility import GenericObservationFacility, GenericObservationForm

# Site data matches built-in pyephem observer data for Los Angeles
SITES = {
    'Los Angeles': {
        'latitude': 34.052222,
        'longitude': -117.756306,
        'elevation': 86.847092
    },
    'Siding Spring': {
        'sitecode': 'coj',
        'latitude': -31.272,
        'longitude': 149.07,
        'elevation': 1116
    },
}


class FakeFacilityForm(GenericObservationForm):
    test_input = forms.CharField(help_text='fake form input')


class FakeFacility(GenericObservationFacility):
    name = 'FakeFacility'
    form = FakeFacilityForm

    @classmethod
    def get_observing_sites(clz):
        return SITES

    @classmethod
    def get_observation_url(clzz, observation_id):
        return ''

    @classmethod
    def data_products(clz, observation_record):
        return [{'id': 'testdpid'}]

    @classmethod
    def get_observation_status(clz, observation_id):
        return 'COMPLETED'

    @classmethod
    def get_terminal_observing_states(clz):
        return ['COMPLETED', 'FAILED', 'CANCELED', 'WINDOW_EXPIRED']

    @classmethod
    def submit_observation(clz, payload):
        return ['fakeid']
