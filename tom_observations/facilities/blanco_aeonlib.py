from typing import Any
from tom_observations.facility import (
    BaseRoboticObservationFacility,
    BaseRoboticObservationForm,
)
from crispy_forms.layout import Div
from tom_observations.observation_template import GenericTemplateForm
from aeonlib.models import SiderealTarget

from pydantic_django_forms.forms import PydanticModelForm


class BlancoObservationForm(PydanticModelForm, BaseRoboticObservationForm):
    class Meta:
        model = SiderealTarget

    def layout(self):
        return Div(
            Div("name", css_class="col"),
            Div("type", css_class="col"),
            Div("ra", css_class="col"),
            Div("dec", css_class="col"),
        )


class BlancoTemplateForm(GenericTemplateForm, BlancoObservationForm):
    pass


class BLANCOAEONFacility(BaseRoboticObservationFacility):
    name = "BLANCOAEON"

    observation_forms = {"OBSERVATION": BlancoObservationForm}

    def data_products(self, observation_id: str, product_id: str = "") -> list[str]:
        return []

    def get_form(self, observation_type: str) -> type[BlancoObservationForm]:
        return self.observation_forms["OBSERVATION"]

    def get_template_form(self, observation_type: str) -> type[BlancoTemplateForm]:
        print("getting template form")
        return BlancoTemplateForm

    def get_observation_status(self, observation_id: str) -> dict[str, Any]:
        return {}

    def get_observation_url(self, observation_id: str) -> str:
        return ""

    def get_observing_sites(self) -> dict:
        return {
            "Blanco: CTIO, Chile": {
                "sitecode": "bco",
                "latitude": -30.16541667,
                "longitude": -70.81463889,
                "elevation": 2000,
            }
        }

    def get_terminal_observing_states(self) -> list:
        return []

    def submit_observation(self, observation_payload: dict) -> dict[str, Any]:
        return {}

    def validate_observation(self, observation_payload: dict) -> dict[str, Any]:
        return
