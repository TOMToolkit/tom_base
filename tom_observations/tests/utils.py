from django import forms
from datetime import timedelta
from django.utils import timezone

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

    def get_observing_sites(self):
        return SITES

    def get_observation_url(self, observation_id):
        return ''

    def data_products(self, observation_record):
        return [{'id': 'testdpid'}]

    def get_observation_status(self, observation_id):
        return {
            'state': 'COMPLETED',
            'scheduled_start': timezone.now() + timedelta(hours=1),
            'scheduled_end': timezone.now() + timedelta(hours=2)
        }

    def get_terminal_observing_states(self):
        return ['COMPLETED', 'FAILED', 'CANCELED', 'WINDOW_EXPIRED']

    def submit_observation(self, payload):
        return ['fakeid']

    def validate_observation(self, observation_payload):
        return True
