from datetime import timedelta

from django import forms
from django.utils import timezone
from astropy import units

from tom_observations.facility import BaseRoboticObservationFacility, GenericObservationForm
from tom_observations.facility import BaseManualObservationFacility
from tom_observations.models import ObservationRecord
from tom_observations.observation_template import GenericTemplateForm

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
    test_input = forms.CharField(help_text='fake form input', required=True)


class FakeFacilityTemplateForm(GenericTemplateForm):
    pass


class FakeRoboticFacility(BaseRoboticObservationFacility):
    name = 'FakeRoboticFacility'
    observation_forms = {
        'OBSERVATION': FakeFacilityForm
    }

    def get_form(self, observation_type):
        return self.observation_forms[observation_type]

    def get_template_form(self, observation_type):
        return FakeFacilityTemplateForm

    def get_observing_sites(self):
        return SITES

    def get_observation_url(self, observation_id):
        return ''

    def data_products(self, observation_id, product_id=None):
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

    def cancel_observation(self, observation_id):
        obsr = ObservationRecord.objects.get(observation_id=observation_id)
        obsr.status = 'CANCELED'
        obsr.save()
        return True

    def get_flux_constant(self):
        return units.erg / units.angstrom

    def get_wavelength_units(self):
        return units.angstrom

    def validate_observation(self, observation_payload):
        return True


class FakeManualFacility(BaseManualObservationFacility):
    name = 'FakeManualFacility'
    observation_forms = {
        'OBSERVATION': FakeFacilityForm
    }

    def get_form(self, observation_type):
        return FakeFacilityForm

    def get_template_form(self, observation_type):
        return FakeFacilityTemplateForm

    def get_observing_sites(self):
        return SITES

    def get_observation_url(self, observation_id):
        return ''

    def data_products(self, observation_id, product_id=None):
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

    def get_flux_constant(self):
        return units.erg / units.angstrom

    def get_wavelength_units(self):
        return units.angstrom

    def validate_observation(self, observation_payload):
        return True

    # TOOD: this method does not belong to this Subclass of BaseObservationFacility
    # it's only here to satisfy tests.test_update_observations() which makes a (now)
    # invalid assumption that all facilities are robotic and have this method
    # The underlying problem is that when an ObservationRecord gets its facility
    # class, it assumes that it's a BaseRoboticFacility subclass.
    def update_all_observation_statuses(self, target):
        return []
