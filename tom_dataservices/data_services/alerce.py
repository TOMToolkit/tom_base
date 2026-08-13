import logging

from alerce.core import Alerce
from alerce.exceptions import ObjectNotFoundError, APIError
from astropy.time import Time, TimezoneInfo
from django import forms
from django.core.cache import cache
from django.db.utils import IntegrityError

import numpy as np
import pyvo

from tom_dataproducts.models import PhotometryReducedDatum
from tom_dataservices.dataservices import DataService, QueryServiceError
from tom_dataservices.forms import BaseQueryForm
from tom_targets.models import Target, TargetExtra

logger = logging.getLogger(__name__)

alerce = Alerce()
TAP_URL = 'https://tap.alerce.online/tap'
tap_service = pyvo.dal.TAPService(TAP_URL)
ALERCE_FILTERS = {1: "g", 2: "r", 3: "i"}


def _to_native_types(record: dict) -> dict:
    """
    TAP query results (astropy Table rows) come back with numpy scalar types
    (np.float64, np.int64, etc.) which aren't accepted by Django model fields
    or JSON-serializable. Convert them to their native Python equivalents.
    """
    return {k: (v.item() if isinstance(v, np.generic) else v) for k, v in record.items()}


def _normalize_tap_record(record: dict) -> dict:
    """
    Converts numpy scalars to native types and renames the TAP `object` table's
    `n_det` column to `ndet`, matching the ALeRCE REST API naming used downstream
    (results table, target extras).
    """
    record = _to_native_types(record)
    if "n_det" in record:
        record["ndet"] = record.pop("n_det")
    return record


def _normalize_ztf_record(record: dict) -> dict:
    """
    Renames the ZTF REST client's `deltajd` field to `deltamjd`, matching the TAP
    `object` table naming (and the `firstmjd`/`lastmjd` naming already used elsewhere)
    so downstream code sees one consistent field name regardless of survey.
    """
    if "deltajd" in record:
        record["deltamjd"] = record.pop("deltajd")
    return record


def _build_tap_object_query(query_parameters: dict, page_size: int = 20) -> str:
    """
    Builds an ADQL query against `alerce_tap.object` for LSST (sid != 0) general
    (non-oid) queries, consuming the same query_parameters shape produced by
    `AlerceDataService.build_query_parameters`. Only numeric parameters (already
    cleaned by the form) are interpolated, so there is no string-injection surface;
    `oid` lookups are handled separately and are not built here.
    """
    sid = query_parameters.get("sid", 0)
    query = f"SELECT TOP {page_size} * FROM alerce_tap.object WHERE sid = {sid}"

    if all(query_parameters.get(k) is not None for k in ("ra", "dec", "radius")):
        ra = query_parameters["ra"]
        dec = query_parameters["dec"]
        radius_deg = query_parameters["radius"] / 3600.0
        query += (
            f" AND 1 = CONTAINS(POINT('ICRS', meanra, meandec), "
            f"CIRCLE('ICRS', {ra}, {dec}, {radius_deg}))"
        )

    if firstmjd := query_parameters.get("firstmjd"):
        query += f" AND firstmjd >= {firstmjd[0]} AND firstmjd <= {firstmjd[1]}"

    if lastmjd := query_parameters.get("lastmjd"):
        query += f" AND lastmjd >= {lastmjd[0]} AND lastmjd <= {lastmjd[1]}"

    if ndet := query_parameters.get("ndet"):
        query += f" AND n_det >= {ndet[0]}"
        if len(ndet) == 2:
            query += f" AND n_det <= {ndet[1]}"

    return query


SURVEY_TID = {"ZTF": 0, "LSST": 1}


def _group_tap_classifier_rows(rows) -> list[dict]:
    """
    Groups `alerce_tap.classifier` JOIN `alerce_tap.taxonomy` rows into the shape
    the (deprecated) REST `query_classifiers()` used to return:
    [{classifier_name, classifier_version, classes: [...]}, ...]
    """
    grouped = {}
    for row in rows:
        row = dict(row)
        key = (row["classifier_name"], row["classifier_version"])
        grouped.setdefault(
            key,
            {
                "classifier_name": row["classifier_name"],
                "classifier_version": row["classifier_version"],
                "classes": [],
            },
        )
        grouped[key]["classes"].append(row["class_name"])
    return list(grouped.values())


class AlerceForm(BaseQueryForm):
    CLASSIFIER_FIELD_PREFIX = "cfield_"

    survey = forms.ChoiceField(
        label="Survey", choices=[("ZTF", "ZTF"), ("LSST", "LSST")], initial="ZTF",
        widget=forms.Select(attrs={"x-model": "survey"}),
    )
    lsst_object_type = forms.ChoiceField(
        required=False,
        label="LSST Object Type",
        choices=[("diaObject", "diaObject"), ("ssObject", "ssObject")],
        initial="diaObject",
        help_text="Only used when Survey is LSST.",
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
        # self.fields['survey'].widget = forms.HiddenInput()

    def get_classifiers(self) -> list[dict]:
        tid = SURVEY_TID.get(self._current_survey(), SURVEY_TID["ZTF"])
        cache_key = f"ds_alerce_classifiers_{tid}"
        classifiers = cache.get(cache_key)
        if not classifiers:
            query = '''
                SELECT c.classifier_name, c.classifier_version, t.class_name
                FROM alerce_tap.classifier c
                JOIN alerce_tap.taxonomy t ON t.classifier_id = c.classifier_id
                WHERE c.tid = %d ORDER BY c.classifier_name, t.taxonomy_order
                ''' % tid
            classifiers = _group_tap_classifier_rows(tap_service.search(query))
            cache.set(cache_key, classifiers, 3600 * 24)  # One day

        return classifiers

    def _current_survey(self) -> str:
        """
        The survey selected on this form instance, bound or not, used to pick the TAP
        `tid` for get_classifiers(). Falls back to the field's initial value (ZTF).
        """
        survey = self.data.get("survey") if self.is_bound else self.initial.get("survey")
        return survey or self.fields["survey"].initial

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
        # Get the sid from the query parameters, defaulting to 0 (ZTF) if not provided
        sid = query_parameters.get("sid", 0)
        try:
            if query_parameters.get("oid"):
                if sid == 0:
                    query_parameters.pop("sid", None)
                    object_result = alerce.query_objects(**query_parameters)
                    object_result = _normalize_ztf_record(object_result)
                else:
                    query = '''
                        SELECT * FROM alerce_tap.object
                        WHERE oid = %s AND sid = %d
                        ''' % (query_parameters.get("oid"), sid)
                    object_result = tap_service.search(query)
                    object_result = _normalize_tap_record(dict(object_result[0]))
                if object_result:
                    results.append(object_result)

                    return results

            elif sid != 0:
                # LSST (diaObject/ssObject) general queries go through TAP; classifier
                # queries against LSST objects are not yet supported.
                if query_parameters.get("classifiers"):
                    raise QueryServiceError("LSST classifier queries not yet supported")
                tap_query = _build_tap_object_query(query_parameters)
                results = [_normalize_tap_record(dict(row)) for row in tap_service.search(tap_query)]

            else:
                # "sid" is only used for the TAP-based object ID lookup above; the ALeRCE
                # REST client used below doesn't accept it.
                query_parameters.pop("sid", None)
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
                results = [_normalize_ztf_record(result) for result in results]
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
        survey = form_parameters.get("survey", "ZTF")
        query_params = {
            "format": "json",
            "survey": survey.lower(),
        }
        if survey == "LSST":
            lsst_object_type = form_parameters.get("lsst_object_type") or "diaObject"
            query_params["sid"] = 2 if lsst_object_type == "ssObject" else 1
        else:
            query_params["sid"] = 0
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
                try:
                    reduced_datum, __ = PhotometryReducedDatum.objects.get_or_create(
                        timestamp=mjd.to_datetime(TimezoneInfo()),
                        target=target,
                        brightness=detection["magpsf"],
                        brightness_error=detection["sigmapsf"],
                        unit='mag',
                        bandpass=ALERCE_FILTERS[detection["fid"]],
                        defaults={'source_name': self.name}
                    )
                    reduced_datums.append(reduced_datum)
                except IntegrityError as e:
                    raise QueryServiceError(f"Error importing ReducedDatum (target:{target} data:{detection}) -- {e}")

            for non_detection in data.get("non_detections", []):
                mjd = Time(non_detection["mjd"], format="mjd", scale="utc")
                reduced_datum, __ = PhotometryReducedDatum.objects.get_or_create(
                    timestamp=mjd.to_datetime(TimezoneInfo()),
                    target=target,
                    limit=non_detection["diffmaglim"],
                    unit='mag',
                    bandpass=ALERCE_FILTERS[non_detection["fid"]],
                    defaults={'source_name': self.name}
                )
                reduced_datums.append(reduced_datum)
        return reduced_datums
