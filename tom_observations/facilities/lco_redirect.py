from urllib.parse import urljoin
import logging
import urllib.parse

from django.conf import settings
from django.shortcuts import get_object_or_404

from tom_observations.facility import BaseRedirectObservationFacility
from tom_observations.facilities.lco import LCOFacility
from tom_observations.facilities.ocs import make_request
from tom_observations.models import ObservationRecord, ObservationGroup
from tom_targets.models import Target

logger = logging.getLogger(__name__)


class LCORedirectFacility(BaseRedirectObservationFacility):
    """
    The ``LCORedirectFacility`` is a little different from the other TOMToolkit Facilities. This facility temporarily
    redirects users from the TOM to the LCO observing portal, providing them with full access to the observation request
    options provided by that interface. Once the observation, or group of observations, are submitted, the user is
    redirected back to the TOM. The user must have access to the LCO observing portal, but will log in with their own
    credentials, rather than those stored by the TOM. In order to retrieve the observations, the TOM must have access
    to an LCO API token with permission to access the relevant proposals.

    For more information on submitting to LCO, Soar, or Blanco, see the
    `LCO Documentation <https://lco.global/documentation/>`__ .
    To use this facility you will need to add it to your `TOM_FACILITY_CLASSES` list in ``settings.py`` and have an
    `api_key` in your `LCO` dictionary in `FACILITIES`:


    .. code-block:: python
        :caption: settings.py

        TOM_FACILITY_CLASSES = [
            ...
            'tom_observations.facilities.LCORedirectFacility',
            ...
            ]

        FACILITIES = {
            'LCO': {
                'portal_url': 'https://observe.lco.global',
                'api_key': os.getenv('LCO_API_KEY'),
            },
        }

    """
    name = "LCORedirect"
    observation_types = [("Default", "")]
    button_label = "LCO/SOAR/BLANCO"
    button_tooltip = "Redirect to LCO/SOAR/BLANCO observation portal"

    def __init__(self, *args, **kwargs):
        self.lco_facility = LCOFacility(name_override=self.name)

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

    def update_all_observation_statuses(self, *args, **kwargs):
        return self.lco_facility.update_all_observation_statuses(*args, **kwargs)

    def get_observation_url(self, observation_id):
        return self.lco_facility.get_observation_url(observation_id)

    def get_terminal_observing_states(self):
        return self.lco_facility.get_terminal_observing_states()

    def get_observing_sites(self):
        return self.lco_facility.get_observing_sites()

    def get_observation_status(self, observation_id):
        return self.lco_facility.get_observation_status(observation_id)

    def data_products(self, observation_id, product_id=None):
        return self.lco_facility.data_products(observation_id, product_id)

    def request_id_to_group(self, observation_id, user, target, parameters):
        """
        The OCS groups individual requests into a single RequestGroup, which is the ID it passes
        back. This method is responsible for querying the individual request IDs associated with
        the RequestGroup and mapping them to an ObservationGroup/ObservationRecord in the TOM.
        """
        # Retrieve the RequestGroup from the OCS API
        response = make_request(
            'GET',
            urljoin(self.observation_portal_url(), f'/api/requestgroups/{observation_id}/'),
            headers=self.lco_facility._portal_headers()
        )
        response.raise_for_status()
        response = response.json()
        # Create observation group - maps to OCS RequestGroup
        observation_group = ObservationGroup.objects.create(
                name=response['name']
        )
        # Create and associate observation records for each child request
        for request in response['requests']:
            obs_record = ObservationRecord.objects.create(
                facility=self.name,
                user=user,
                target=target,
                observation_id=request['id'],
                parameters=parameters
            )
            observation_group.observation_records.add(obs_record)

        return observation_group
