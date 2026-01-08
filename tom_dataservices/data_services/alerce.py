from alerce.core import Alerce
from crispy_forms.layout import HTML, Column, Field, Layout, Row
from django import forms
from django.core.cache import cache

from tom_dataservices.dataservices import BaseDataService
from tom_dataservices.forms import BaseQueryForm

alerce = Alerce()


class AlerceForm(BaseQueryForm):
    CLASSIFIER_FIELD_PREFIX = "cfield_"

    survey = forms.ChoiceField(
        label="Survey", choices=[("ZTF", "ZTF"), ("LSST", "LSST")]
    )
    object_id = forms.CharField(required=False, label="Object ID")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        classifier_fields = self.add_classifiers_fields()
        # Static fields layout
        layout_fields = [Field("survey"), Field("object_id")]
        # Dynamic 2-column layout
        for i in range(0, len(classifier_fields), 2):
            if i + 1 < len(classifier_fields):
                layout_fields.append(
                    Row(
                        Column(Field(classifier_fields[i])),
                        Column(Field(classifier_fields[i + 1])),
                    )
                )
            else:
                layout_fields.append(Row(Column(Field(classifier_fields[i]))))

        self.helper.layout = Layout(
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

    def add_classifiers_fields(self) -> list[str]:
        classifiers = self.get_classifiers()
        field_names = []
        for c in classifiers:
            field_name = f"{self.CLASSIFIER_FIELD_PREFIX}{c['classifier_name']}"
            self.fields[field_name] = forms.ChoiceField(
                choices=[(None, "")] + [(k, k) for k in c["classes"]],
                required=False,
                help_text=c["classifier_version"],
            )
            field_names.append(field_name)

        return field_names

    def clean(self):
        cleaned_data = super().clean()
        classifier_name = None
        classifier_class = None
        object_id = cleaned_data.get("object_id")

        # Find the classifier, if any
        for (k, v) in cleaned_data.items():
            if k.startswith(self.CLASSIFIER_FIELD_PREFIX) and v:
                if classifier_name or classifier_class:
                    raise forms.ValidationError("At most one classifier can be selected.")
                else:
                    classifier_name = k.split(self.CLASSIFIER_FIELD_PREFIX)[1]
                    classifier_class = v

        # Make sure only object_id or classifier is provided
        if classifier_name and object_id:
            raise forms.ValidationError("Choose either an object or a classifier.")
        elif classifier_name:
            cleaned_data["classifier_name"] = classifier_name
            cleaned_data["classifier_class"] = classifier_class
            return cleaned_data
        elif object_id:
            cleaned_data["object_id"] = object_id
            return cleaned_data
        else:
            raise forms.ValidationError("Choose either an object or a classifier.")


class AlerceDataService(BaseDataService):
    name = "Alerce"

    @classmethod
    def get_form_class(cls):
        return AlerceForm

    def query_service(self, query_parameters, **kwargs):
        print("query_service", query_parameters)
        return []

    def build_query_parameters(self, parameters: dict, **kwargs):
        print("build_query_parameters", parameters)
        return {}
