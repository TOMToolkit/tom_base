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


def _append_tap_filters(query: str, query_parameters: dict, column_prefix: str = "") -> str:
    """
    Appends the cone-search / mjd-range / ndet-range WHERE clauses shared by all
    `alerce_tap.object`-based ADQL queries. `column_prefix` (e.g. `"obj."`) is
    needed when `alerce_tap.object` is joined/aliased, as in
    `_build_tap_classifier_query`. Only numeric parameters (already cleaned by
    the form) are interpolated, so there is no string-injection surface.
    """
    p = column_prefix
    if all(query_parameters.get(k) is not None for k in ("ra", "dec", "radius")):
        ra = query_parameters["ra"]
        dec = query_parameters["dec"]
        radius_deg = query_parameters["radius"] / 3600.0
        query += (
            f" AND 1 = CONTAINS(POINT('ICRS', {p}meanra, {p}meandec), "
            f"CIRCLE('ICRS', {ra}, {dec}, {radius_deg}))"
        )

    if firstmjd := query_parameters.get("firstmjd"):
        query += f" AND {p}firstmjd >= {firstmjd[0]} AND {p}firstmjd <= {firstmjd[1]}"

    if lastmjd := query_parameters.get("lastmjd"):
        query += f" AND {p}lastmjd >= {lastmjd[0]}"
        if len(lastmjd) == 2:
            query += f" AND {p}lastmjd <= {lastmjd[1]}"

    if ndet := query_parameters.get("ndet"):
        query += f" AND {p}n_det >= {ndet[0]}"
        if len(ndet) == 2:
            query += f" AND {p}n_det <= {ndet[1]}"

    return query


def _build_tap_object_query(query_parameters: dict, page_size: int = 20) -> str:
    """
    Builds an ADQL query against `alerce_tap.object` for LSST (sid != 0) general
    (non-oid) queries, consuming the same query_parameters shape produced by
    `AlerceDataService.build_query_parameters`. `oid` lookups are handled
    separately and are not built here.
    """
    sid = query_parameters.get("sid", 0)
    query = f"SELECT TOP {page_size} * FROM alerce_tap.object WHERE sid = {sid}"
    return _append_tap_filters(query, query_parameters)


def _build_tap_classifier_query(
    query_parameters: dict, classifier_id: int, class_id: int, probability: float | None = None,
    page_size: int = 20,
) -> str:
    """
    Builds an ADQL query joining `alerce_tap.object` to `alerce_tap.probability`
    for LSST diaObject (sid=1) classifier queries -- the TAP equivalent of the
    ZTF REST classifier loop in `query_service`. `ranking = 1` restricts results
    to objects whose *top-ranked* classification is the requested class (matching
    ALeRCE's own usage in notebooks/LSST/ALeRCE_LSST_SSO.ipynb); `probability`,
    when given, is treated as a minimum threshold. Only sid=1 is meaningful here:
    known ssObjects (sid=2) are pre-assigned probability 1 "asteroid" rather than
    classified, so classifier queries are not offered for sid=2 (see
    `AlerceDataService.query_service`).
    """
    sid = query_parameters.get("sid", 1)
    query = (
        f"SELECT TOP {page_size} obj.*, prob.probability, prob.ranking "
        f"FROM alerce_tap.object AS obj "
        f"JOIN alerce_tap.probability AS prob "
        f"ON obj.oid = prob.oid AND obj.sid = prob.sid "
        f"WHERE obj.sid = {sid} AND prob.classifier_id = {classifier_id} "
        f"AND prob.class_id = {class_id} AND prob.ranking = 1"
    )
    if probability is not None:
        query += f" AND prob.probability >= {probability}"
    query = _append_tap_filters(query, query_parameters, column_prefix="obj.")
    query += " ORDER BY prob.probability DESC"
    return query


SURVEY_TID = {"ZTF": 0, "LSST": 1}


def _group_tap_classifier_rows(rows) -> list[dict]:
    """
    Groups `alerce_tap.classifier` JOIN `alerce_tap.taxonomy` rows into the shape
    the (deprecated) REST `query_classifiers()` used to return, plus the numeric
    `classifier_id`/`class_id` TAP `probability` queries need (absent from rows
    that don't carry them, e.g. older fixtures):
    [{classifier_name, classifier_version, classifier_id, classes: [...], class_ids: {name: id}}, ...]
    """
    grouped = {}
    for row in rows:
        row = dict(row)
        key = (row["classifier_name"], row["classifier_version"])
        grouped.setdefault(
            key,
            {
                "classifier_id": row.get("classifier_id"),
                "classifier_name": row["classifier_name"],
                "classifier_version": row["classifier_version"],
                "classes": [],
                "class_ids": {},
            },
        )
        grouped[key]["classes"].append(row["class_name"])
        if "class_id" in row:
            grouped[key]["class_ids"][row["class_name"]] = row["class_id"]
    return list(grouped.values())


def _fetch_classifiers_for_tid(tid: int) -> list[dict]:
    """
    Queries + caches (24h) `alerce_tap.classifier` JOIN `alerce_tap.taxonomy` for a
    given `tid`, grouped via `_group_tap_classifier_rows`. Shared by
    `AlerceForm.get_classifiers` (form field generation) and
    `_resolve_classifier_ids` (TAP classifier-query construction) so both see the
    same cached data under the same cache key.
    """
    cache_key = f"ds_alerce_classifiers_{tid}"
    classifiers = cache.get(cache_key)
    if not classifiers:
        query = '''
            SELECT c.classifier_id, c.classifier_name, c.classifier_version,
                   t.class_id, t.class_name
            FROM alerce_tap.classifier c
            JOIN alerce_tap.taxonomy t ON t.classifier_id = c.classifier_id
            WHERE c.tid = %d ORDER BY c.classifier_name, t.taxonomy_order
            ''' % tid
        classifiers = _group_tap_classifier_rows(tap_service.search(query))
        cache.set(cache_key, classifiers, 3600 * 24)  # One day
    return classifiers


def _resolve_classifier_ids(tid: int, classifier_name: str, class_name: str) -> tuple[int, int] | None:
    """
    Looks up the numeric (classifier_id, class_id) pair for a classifier/class
    name pair, as needed to query `alerce_tap.probability`. Returns None if no
    match is found (e.g. a stale classifier name from a different survey/tid).
    """
    for classifier in _fetch_classifiers_for_tid(tid):
        if classifier["classifier_name"] == classifier_name and class_name in classifier["class_ids"]:
            return classifier["classifier_id"], classifier["class_ids"][class_name]
    return None


class AlerceForm(BaseQueryForm):
    CLASSIFIER_FIELD_PREFIX = "cfield_"

    survey = forms.ChoiceField(
        label="Survey", choices=[("ZTF", "ZTF"), ("LSST", "LSST")], initial="ZTF",
        widget=forms.Select(attrs={"x-model": "$store.alerce.survey"}),
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

    def get_classifiers(self, survey: str) -> list[dict]:
        tid = SURVEY_TID.get(survey, SURVEY_TID["ZTF"])
        return _fetch_classifiers_for_tid(tid)

    def add_classifiers_fields(self) -> list[tuple[str, str]]:
        """
        Adds classifier fields for *every* survey (not just whichever one happens to be
        selected/initial), so the advanced form can show/hide the right classifier set
        purely client-side (via Alpine, keyed off the `survey` field) when the user
        switches surveys, without a full form re-render. Field names embed the owning
        survey (`cfield_{survey}__{classifier_name}`) so `clean()` can tell which group a
        submitted value belongs to and ignore stale values left in a hidden,
        non-selected survey's fields.
        Returns a list of classifier, probability fields name pairs to be used
        by the crispy layout.
        """
        field_names = []
        for survey in SURVEY_TID:
            for c in self.get_classifiers(survey):
                field_name = f"{self.CLASSIFIER_FIELD_PREFIX}{survey}__{c['classifier_name']}"
                # Add the field to the Django form
                self.fields[field_name] = forms.ChoiceField(
                    label=f"{c['classifier_name']}",
                    choices=[(None, "")] + [(k, k) for k in c["classes"]],
                    required=False,
                    help_text=f'Classifier Version: {c["classifier_version"]}',
                )
                prob_field_name = f"prob_{field_name}"
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
        selected_survey = cleaned_data.get("survey")
        classifiers: list[dict] = []

        # Find the classifiers, if any, belonging to the currently selected survey.
        # (Non-selected surveys' classifier fields are present in the form -- so they
        # can be toggled client-side -- but merely hidden, not disabled, so a stale
        # value left over from switching surveys must be ignored here.)
        for k, v in cleaned_data.items():
            if k.startswith(self.CLASSIFIER_FIELD_PREFIX) and v:
                survey, classifier_name = k[len(self.CLASSIFIER_FIELD_PREFIX):].split("__", 1)
                if survey != selected_survey:
                    continue
                classifiers.append(
                    {
                        "classifier": classifier_name,
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
                # LSST (diaObject/ssObject) general queries go through TAP. Classifier
                # queries are only meaningful for diaObjects (sid=1): known ssObjects
                # (sid=2) are pre-assigned probability 1 "asteroid" rather than
                # classified (see alerce_tap.probability / ALeRCE's own LSST SSO
                # notebook), so they're not offered here.
                classifier_params = query_parameters.get("classifiers")
                if classifier_params:
                    if sid != 1:
                        raise QueryServiceError("LSST classifier queries are only supported for diaObjects")
                    tid = SURVEY_TID["LSST"]
                    for classifier in classifier_params:
                        ids = _resolve_classifier_ids(tid, classifier["classifier"], classifier["class"])
                        if ids is None:
                            raise QueryServiceError(
                                f"Unknown ALeRCE LSST classifier/class: "
                                f"{classifier['classifier']}/{classifier['class']}"
                            )
                        classifier_id, class_id = ids
                        tap_query = _build_tap_classifier_query(
                            query_parameters, classifier_id, class_id, classifier.get("probability")
                        )
                        results.extend(_normalize_tap_record(dict(row)) for row in tap_service.search(tap_query))
                else:
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
        # lastmjd supports an open-ended lower bound (e.g. "last detected after X",
        # a common recency filter -- see ALeRCE's own LSST TAP queries notebook),
        # unlike firstmjd above which only makes sense as a closed range.
        if lastmjd_gt := form_parameters.get("lastmjd_gt"):
            lastmjd_lt = form_parameters.get("lastmjd_lt")
            query_params["lastmjd"] = [lastmjd_gt, lastmjd_lt] if lastmjd_lt else [lastmjd_gt]

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
