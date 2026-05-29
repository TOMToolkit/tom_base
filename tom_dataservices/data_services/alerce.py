import logging

from alerce.core import Alerce
from alerce.exceptions import ObjectNotFoundError, APIError
from astropy.time import Time, TimezoneInfo
from django import forms
from django.core.cache import cache

from tom_dataproducts.models import ReducedDatum
from tom_dataservices.dataservices import DataService, QueryServiceError
from tom_dataservices.forms import BaseQueryForm
from tom_targets.models import Target, TargetExtra

logger = logging.getLogger(__name__)

alerce = Alerce()

ALERCE_FILTERS = {1: "g", 2: "r", 3: "i"}


class AlerceForm(BaseQueryForm):
    CLASSIFIER_FIELD_PREFIX = "cfield_"

    survey = forms.ChoiceField(
        label="Survey", choices=[("ZTF", "ZTF"), ("LSST", "LSST")], initial="ZTF"
    )
    object_id = forms.CharField(required=False, label="Object ID")
    ra = forms.FloatField(required=False, label="RA (deg)")
    dec = forms.FloatField(required=False, label="Dec (deg)")
    radius = forms.FloatField(required=False, label="Search Radius (arcsec)")
    firstmjd_gt = forms.FloatField(required=False, label="Min MJD of first detection")
    firstmjd_lt = forms.FloatField(required=False, label="Max MJD of first detection")
    lastmjd_gt = forms.FloatField(required=False, label="Min MJD of last detection")
    lastmjd_lt = forms.FloatField(required=False, label="Max MJD of last detection")
    ndet_min = forms.IntegerField(required=False, label="Min. Number of Detections")
    ndet_max = forms.IntegerField(required=False, label="Max Number of Detections")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Dynamically add the classifier fields to the form
        self.add_classifiers_fields()
        # Make the survey field hidden for now until the LSST API is more featured
        self.fields['survey'].widget = forms.HiddenInput()

    def get_classifiers(self) -> list[dict]:
        classifiers = cache.get("ds_alerce_classifiers")
        if not classifiers:
            classifiers = alerce.query_classifiers()
            cache.set("ds_alerce_classifiers", classifiers, 3600 * 24)  # One day

        return classifiers

    def add_classifiers_fields(self) -> list[tuple[str, str]]:
        """
        Adds the fields dynamically to the form.
        Returns a list of classifier, probability fields name pairs to be used
        by the crispy layout.
        """
        classifiers = self.get_classifiers()
        field_names = []
        for c in classifiers:
            field_name = f"{self.CLASSIFIER_FIELD_PREFIX}{c['classifier_name']}"
            # Add the field to the Django form
            self.fields[field_name] = forms.ChoiceField(
                label=f"{c['classifier_name']}",
                choices=[(None, "")] + [(k, k) for k in c["classes"]],
                required=False,
                help_text=f'Classifier Version: {c["classifier_version"]}',
            )
            prob_field_name = (
                f"prob_{self.CLASSIFIER_FIELD_PREFIX}{c['classifier_name']}"
            )
            self.fields[prob_field_name] = forms.FloatField(
                label=f"{c['classifier_name']} Probability",
                required=False,
                max_value=1,
                min_value=0,
                help_text="Value between 0 and 1"
            )
            field_names.append((field_name, prob_field_name))

        # Returns field names, not the actual field objects
        return field_names

    def clean(self):
        cleaned_data = super().clean() or {}
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

    def get_simple_form_partial(self):
        return "tom_dataservices/alerce/partials/alerce_simple_form.html"

    def get_advanced_form_partial(self):
        return "tom_dataservices/alerce/partials/alerce_advanced_form.html"


class AlerceDataService(DataService):
    name = "ALeRCE"
    query_results_table = "tom_dataservices/alerce/partials/alerce_results_table.html"

    @classmethod
    def get_form_class(cls):
        return AlerceForm

    def query_targets(self, query_parameters, **kwargs) -> list[dict]:
        targets = self.query_service(query_parameters, **kwargs)
        return targets

    def query_service(self, query_parameters, **kwargs) -> list[dict]:
        """
        Uses the object ID and list of classifiers to query the ALeRCE API.
        Will query the api once for each classifier specified as well as object ID
        if provided.
        """
        results = []
        try:
            if query_parameters.get("oid"):
                # We might want to specify the survey based on the object id prefix
                # once the LSST support in the alerce client is improved
                object_result = alerce.query_object(**query_parameters)
                if object_result:
                    results.append(object_result)

                    return results

            classifier_params = query_parameters.pop("classifiers")
            if len(classifier_params) == 0:
                general_results = alerce.query_objects(**query_parameters).get("items", [])
                results.extend(general_results)
            else:
                for classifier in classifier_params:
                    classifier_results = alerce.query_objects(
                        classifier=classifier["classifier"],
                        class_name=classifier["class"],
                        probability=classifier["probability"],
                        **query_parameters,
                    ).get("items", [])
                    results.extend(classifier_results)
        except (ObjectNotFoundError, ValueError, APIError) as e:
            raise QueryServiceError(str(e))

        for result in results:
            result["survey"] = query_parameters["survey"]

        return results

    def build_query_parameters(self, parameters: dict, **kwargs):
        """
        Creates a list of query parameters that can be understood by the ALeRCE client in query_service
        based on the input from the form.
        See https://alerce.readthedocs.io/en/stable/ for details.
        """
        form_parameters = parameters
        query_params = {
            "format": "json",
            "survey": form_parameters.get("survey", "").lower(),
        }
        if (firstmjd_gt := form_parameters.get("firstmjd_gt")) and (
            firstmjd_lt := form_parameters.get("firstmjd_lt")
        ):
            query_params["firstmjd"] = [firstmjd_gt, firstmjd_lt]
        if (lastmjd_gt := form_parameters.get("lastmjd_gt")) and (
            lastmjd_lt := form_parameters.get("lastmjd_lt")
        ):
            query_params["lastmjd"] = [lastmjd_gt, lastmjd_lt]

        # Build ndet list:
        # gives range of number of detections based on min/max set in form.
        ndet_min = form_parameters.get("ndet_min")
        if ndet_max := form_parameters.get("ndet_max"):
            if not ndet_min:
                ndet_min = 0
            query_params["ndet"] = [ndet_min, ndet_max]
        elif ndet_min:
            query_params["ndet"] = [ndet_min,]

        if all(
            [
                ra := form_parameters.get("ra"),
                dec := form_parameters.get("dec"),
                radius := form_parameters.get("radius"),
            ]
        ):
            query_params["ra"] = ra
            query_params["dec"] = dec
            query_params["radius"] = radius

        if form_parameters.get("object_id"):
            query_params["oid"] = form_parameters.get("object_id")
        query_params["classifiers"] = form_parameters.get("classifiers", [])
        return query_params

    def build_query_parameters_from_target(self, target, **kwargs):
        query_parameters = {"object_id": target.name}
        try:
            query_parameters["classifiers"] = [
                target.targetextra_set.get(key="classifier").value
            ]
            query_parameters["survey"] = target.targetextra_set.get(key="survey").value
        except TargetExtra.DoesNotExist:
            if target.name.startswith("ZTF"):
                query_parameters["survey"] = "ZTF"
            else:
                query_parameters["survey"] = "LSST"
        return query_parameters

    def create_target_from_query(self, target_result: dict, **kwrags):
        target = Target(
            name=target_result["oid"],
            type="SIDEREAL",
            ra=target_result["meanra"],
            dec=target_result["meandec"],
        )
        return target

    def create_target_extras_from_query(self, query_results, **kwrags):
        """
        All fields except for the ones stored on the target model
        """
        return {
            k: v
            for k, v in query_results.items()
            if k not in ["oid", "meanra", "meandec"]
        }

    def query_photometry(self, query_parameters, **kwargs):
        try:
            return alerce.query_lightcurve(
                oid=query_parameters.get("object_id"),
                survey=query_parameters.get("survey", "").lower(),
                format="json",
            )
        except Exception as e:
            logger.exception(f"Error querying ALeRCE photometry: {e}")
            return {}

    def query_spectroscopy(self, query_parameters, **kwargs):
        return {}

    def query_forced_photometry(self, query_parameters, **kwargs):
        try:
            return alerce.query_forced_photometry(
                oid=query_parameters.get("object_id"),
                survey=query_parameters.get("survey", "").lower(),
                format="json",
            )
        except Exception:
            logger.exception("Error querying ALeRCE forced photometry")
            return []

    def create_reduced_datums_from_query(self, target, data=None, data_type="photometry", **kwargs):
        reduced_datums = []
        if data:
            for detection in data.get("detections", []):
                mjd = Time(detection["mjd"], format="mjd", scale="utc")
                value = {
                    "filter": ALERCE_FILTERS[detection["fid"]],
                    "magnitude": detection["magpsf"],
                    "error": detection["sigmapsf"],
                    "telescope": "ZTF",
                }
                reduced_datum, __ = ReducedDatum.objects.get_or_create(
                    timestamp=mjd.to_datetime(TimezoneInfo()),
                    value=value,
                    data_type="photometry",
                    target=target,
                    defaults={'source_name': self.name}
                )
                reduced_datums.append(reduced_datum)

            for non_detection in data.get("non_detections", []):
                mjd = Time(non_detection["mjd"], format="mjd", scale="utc")
                value = {
                    "filter": ALERCE_FILTERS[non_detection["fid"]],
                    "limit": non_detection["diffmaglim"],
                    "telescope": "ZTF",
                }
                reduced_datum, __ = ReducedDatum.objects.get_or_create(
                    timestamp=mjd.to_datetime(TimezoneInfo()),
                    value=value,
                    data_type="photometry",
                    target=target,
                    defaults={'source_name': self.name}
                )
                reduced_datums.append(reduced_datum)
        return reduced_datums
