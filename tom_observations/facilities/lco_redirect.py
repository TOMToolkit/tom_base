import logging
import urllib.parse

from crispy_forms.layout import HTML, Layout
from django.conf import settings
from django.shortcuts import get_object_or_404
from django.urls import reverse

from tom_observations.facility import GenericObservationFacility, GenericObservationForm
from tom_targets.models import Target

logger = logging.getLogger(__name__)


class LCORedirectForm(GenericObservationForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        target_id = self.initial.get('target_id')
        target = get_object_or_404(Target, pk=target_id)
        query_params = self.target_to_query_params(target)
        request = self.initial.get('request', None)
        if not request:
            raise ValueError("LCORedirectForm requires request in initial data")
        redirect_uri = request.build_absolute_uri(
            reverse("tom_observations:callback")
        ) + f"?target_id={target.pk}&facility=LCO"
        redirect_uri = urllib.parse.quote_plus(redirect_uri)
        portal_uri = self.observation_portal_uri()
        url = f"{portal_uri}/create?{query_params}&redirect_uri={redirect_uri}"
        self.helper.layout = Layout(
            HTML(f'''
                <p>
                This plugin will redirect you to the LCO global observation portal to
                create an observation for this target.
                You will be redirected back to the TOM once the observation is submitted.
                </p>
                <a class="btn btn-outline-primary" href="{url}">
                    Continue to lco.global
                </a>
                <a class="btn btn-outline-primary"
                href="{{% url 'tom_targets:detail' {target_id} %}}?tab=observe">Back</a>
            ''')
        )

    def target_to_query_params(self, target) -> str:
        set_fields = {"target_" + k: v for k, v in target.as_dict().items() if v is not None}
        return urllib.parse.urlencode(set_fields)

    def observation_portal_uri(self) -> str:
        return settings.FACILITIES.get('LCO', {}).get('portal_url', 'https://observe.lco.global')


class LCORedirectFacility(GenericObservationFacility):
    name = 'LCORedirect'
    observation_forms = {
        'ALL': LCORedirectForm,
    }
    observation_types = [('Default', '')]

    def get_form(self, observation_type):
        return LCORedirectForm

    def get_template_form(self, observation_type):
        pass

    def submit_observation(self, observation_payload):
        return

    def validate_observation(self, observation_payload):
        return

    def get_observation_url(self, observation_id):
        return

    def get_terminal_observing_states(self):
        return []

    def get_observing_sites(self):
        return {}

    def get_observation_status(self, observation_id):
        return

    def data_products(self, observation_id, product_id=None):
        return []
