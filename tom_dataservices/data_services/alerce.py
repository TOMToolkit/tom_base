from alerce.core import Alerce
from alerce.exceptions import ObjectNotFoundError
from crispy_forms.layout import HTML, Column, Field, Layout, Row
from django import forms
from django.core.cache import cache

from tom_dataservices.dataservices import BaseDataService, QueryServiceError
from tom_dataservices.forms import BaseQueryForm
from tom_targets.models import get_target_model_class

alerce = Alerce()


class AlerceForm(BaseQueryForm):
    CLASSIFIER_FIELD_PREFIX = "cfield_"

    survey = forms.ChoiceField(
        label="Survey", choices=[("ZTF", "ZTF"), ("LSST", "LSST")]
    )
    object_id = forms.CharField(required=False, label="Object ID")

    def get_layout(self, *args, **kwargs) -> Layout:
        classifier_fields = self.add_classifiers_fields()
        # Static fields layout
        layout_fields = [Field("survey"), Field("object_id")]
        for field, prob_field in classifier_fields:
            layout_fields.append(Row(Column(Field(field)), Column(Field(prob_field))))

        return Layout(
            HTML("""
                <p>
                Please see the <a href="http://alerce.science/" target="_blank">ALeRCE homepage</a> for information
                about the ALeRCE filters.
            """),
            *layout_fields,
        )

    def get_classifiers(self) -> list[dict]:
        classifiers = cache.get("ds_alerce_classifiers")
        if not classifiers:
            classifiers = alerce.query_classifiers()
            cache.set("ds_alerce_classifiers", classifiers, 3600 * 24)  # One day

        return classifiers

    def add_classifiers_fields(self) -> list[tuple[str, str]]:
        classifiers = self.get_classifiers()
        field_names = []
        for c in classifiers:
            field_name = f"{self.CLASSIFIER_FIELD_PREFIX}{c['classifier_name']}"
            self.fields[field_name] = forms.ChoiceField(
                label=f"{c['classifier_name']}",
                choices=[(None, "")] + [(k, k) for k in c["classes"]],
                required=False,
                help_text=c["classifier_version"],
            )
            prob_field_name = (
                f"prob_{self.CLASSIFIER_FIELD_PREFIX}{c['classifier_name']}"
            )
            self.fields[prob_field_name] = forms.FloatField(
                label=f"{c['classifier_name']} Probability",
                required=False,
            )
            field_names.append((field_name, prob_field_name))

        return field_names

    def clean(self):
        cleaned_data = super().clean()
        classifiers: list[dict] = []

        # Find the classifiers, if any
        for k, v in cleaned_data.items():
            if k.startswith(self.CLASSIFIER_FIELD_PREFIX) and v:
                classifiers.append(
                    {
                        "classifier": k.split(self.CLASSIFIER_FIELD_PREFIX)[1],
                        "class": v,
                        "probability": cleaned_data.get(f"prob_{k}", None),
                    }
                )
        cleaned_data["classifiers"] = classifiers

        return cleaned_data


class AlerceDataService(BaseDataService):
    name = "Alerce"

    @classmethod
    def get_form_class(cls):
        return AlerceForm

    def query_service(self, query_parameters, **kwargs) -> list[dict]:
        params = {
            "format": "json",
            "survey": query_parameters.get("survey", "").lower(),
        }
        results = []
        try:
            if query_parameters.get("object_id"):
                object_result = alerce.query_object(
                    oid=query_parameters.get("object_id"), **params
                )
                if object_result:
                    results.append(object_result)

            for classifier in query_parameters.get("classifiers", []):
                classifier_results = alerce.query_objects(
                    classifier=classifier["classifier"],
                    class_name=classifier["class"],
                    probability=classifier["probability"],
                    **params,
                ).get("items", [])
                results.extend(classifier_results)
        except (ObjectNotFoundError, ValueError) as e:
            raise QueryServiceError(str(e))

        return results

    def build_query_parameters(self, parameters: dict, **kwargs):
        return {
            "object_id": parameters.get("object_id"),
            "classifiers": parameters.get("classifiers", []),
            "survey": parameters.get("survey"),
        }

    def create_target_from_query(self, target_result: dict, **kwrags):
        Target = get_target_model_class()

        return Target.objects.create(
            name=target_result["oid"],
            type="SIDEREAL",
            ra=target_result["meanra"],
            dec=target_result["meandec"],
        )
