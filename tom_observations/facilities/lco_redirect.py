import logging
import urllib.parse

from django.conf import settings
from django.shortcuts import get_object_or_404

from tom_observations.facility import BaseRedirectObservationFacility
from tom_targets.models import Target

logger = logging.getLogger(__name__)


class LCORedirectFacility(BaseRedirectObservationFacility):
    name = "LCORedirect"
    observation_types = [("Default", "")]

    def target_to_query_params(self, target) -> str:
        set_fields = {
            "target_" + k: v for k, v in target.as_dict().items() if v is not None
        }
        return urllib.parse.urlencode(set_fields)

    def observation_portal_url(self) -> str:
        return settings.FACILITIES.get("LCO", {}).get(
            "portal_url", "https://observe.lco.global"
        )

    def redirect_url(self, target_id, callback_url):
        target = get_object_or_404(Target, pk=target_id)
        query_params = self.target_to_query_params(target)
        callback_url = urllib.parse.quote_plus(callback_url)
        portal_url = self.observation_portal_url()
        url = f"{portal_url}/create?{query_params}&redirect_uri={callback_url}"

        return url

    def get_observation_url(self, observation_id):
        return ""

    def get_terminal_observing_states(self):
        return []

    def get_observing_sites(self):
        return {}

    def get_observation_status(self, observation_id):
        return None

    def data_products(self, observation_id, product_id=None):
        return []
