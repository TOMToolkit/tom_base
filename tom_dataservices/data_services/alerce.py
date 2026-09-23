import logging
import math
import re

from alerce.core import Alerce
from alerce.exceptions import ObjectNotFoundError, APIError
from astropy.constants import GM_sun, au
from astropy.time import Time, TimezoneInfo
from django import forms
from django.core.cache import cache
from django.db.utils import IntegrityError

import numpy as np
import pyvo
import requests

from tom_dataproducts.models import PhotometryReducedDatum
from tom_dataservices.data_services.tns import TNSDataService
from tom_dataservices.dataservices import DataService, NotConfiguredError, QueryServiceError
from tom_dataservices.forms import BaseQueryForm
from tom_targets.models import Target

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
    Appends the cone-search / mjd-range / ndet-range / max-deltamjd WHERE clauses shared by all
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

    if (deltamjd_max := query_parameters.get("deltamjd_max")) is not None:
        query += f" AND {p}deltamjd <= {float(deltamjd_max)}"

    return query


DEFAULT_PAGE_SIZE = 20
MAX_PAGE_SIZE = 1000
# Sort choices offered by AlerceForm, mapped to `alerce_tap.object` columns. The keys are
# also valid ZTF REST `order_by` values.
TAP_ORDER_COLUMNS = {"lastmjd": "lastmjd", "firstmjd": "firstmjd", "ndet": "n_det"}


def _tap_order_clause(query_parameters: dict, column_prefix: str = "") -> str:
    """
    Returns an ` ORDER BY` clause for `query_parameters["order_by"]`/`["order_mode"]`, or
    "" if no (known) order was requested. Only whitelisted columns and ASC/DESC are
    interpolated, since query_parameters can come from saved queries and not only from
    the validated form.
    """
    column = TAP_ORDER_COLUMNS.get(query_parameters.get("order_by"))
    if not column:
        return ""
    mode = "ASC" if query_parameters.get("order_mode") == "ASC" else "DESC"
    return f" ORDER BY {column_prefix}{column} {mode}"


def _build_tap_object_query(query_parameters: dict, page_size: int | None = None) -> str:
    """
    Builds an ADQL query against `alerce_tap.object` for LSST (sid != 0) general
    (non-oid) queries, consuming the same query_parameters shape produced by
    `AlerceDataService.build_query_parameters`. `oid` lookups are handled
    separately and are not built here. The row limit comes from `page_size`, then
    `query_parameters["page_size"]`, then `DEFAULT_PAGE_SIZE`.
    """
    sid = query_parameters.get("sid", 0)
    page_size = int(page_size or query_parameters.get("page_size") or DEFAULT_PAGE_SIZE)
    query = f"SELECT TOP {page_size} * FROM alerce_tap.object WHERE sid = {sid}"
    query = _append_tap_filters(query, query_parameters)
    return query + _tap_order_clause(query_parameters)


def _build_tap_classifier_query(
    query_parameters: dict, classifier_id: int, class_id: int, probability: float | None = None,
    page_size: int | None = None,
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
    `AlerceDataService.query_service`). Results are ordered by descending
    probability unless `query_parameters` asks for another order.
    """
    sid = query_parameters.get("sid", 1)
    page_size = int(page_size or query_parameters.get("page_size") or DEFAULT_PAGE_SIZE)
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
    query += _tap_order_clause(query_parameters, column_prefix="obj.") or " ORDER BY prob.probability DESC"
    return query


SURVEY_TID = {"ZTF": 0, "LSST": 1}
ALERCE_EXPLORER_URLS = {
    "ztf": "https://alerce.online/object/{oid}",
    "lsst": "https://lsst.alerce.online/object/{oid}?survey=lsst",
}


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


# From ALeRCE's `alerce_tap.band` lookup table for tid=1 (identical for sid 1 and 2).
LSST_BANDS = {1: "g", 2: "r", 3: "i", 4: "z", 5: "y", 6: "u"}
LSST_AB_ZEROPOINT_NJY = 31.4


def _lsst_detection_photometry(detection: dict) -> dict | None:
    """
    Converts an LSST detection's difference-image PSF flux (`psfFlux`/`psfFluxErr`,
    in nJy) to PhotometryReducedDatum field values in AB magnitudes. Returns None
    when the flux is non-positive (source fainter than the template), which has no
    magnitude.
    """
    flux = detection.get("psfFlux")
    if flux is None or flux <= 0:
        return None
    flux_err = detection.get("psfFluxErr")
    return {
        "brightness": LSST_AB_ZEROPOINT_NJY - 2.5 * math.log10(flux),
        "brightness_error": 2.5 / math.log(10) * flux_err / flux if flux_err is not None else None,
        "bandpass": detection.get("band_name") or LSST_BANDS[detection["band"]],
        "telescope": "Rubin",
        "instrument": "LSSTCam",
    }


GAUSSIAN_K_DEG_PER_DAY = math.degrees(math.sqrt(GM_sun.value) * au.value ** -1.5 * 86400.0)


def _fetch_lsst_mpc_orbit(ss_object_id) -> dict | None:
    """
    Returns the latest `alerce_tap.lsst_mpc_orbits` record for an LSST ssObjectId, or None
    if ALeRCE has none stored.
    """
    query = f"SELECT * FROM alerce_tap.lsst_mpc_orbits WHERE ssObjectId = {int(ss_object_id)}"
    rows = tap_service.search(query)
    return _to_native_types(dict(rows[0])) if len(rows) else None


LSST_DESIGNATION_PATTERN = re.compile(r"^[A-Za-z0-9 /()\-.]+$")


def _resolve_lsst_designation(designation: str) -> int | None:
    """
    Returns the LSST ssObjectId for an MPC designation as stored by ALeRCE (e.g.
    "2010 WX64"), or None if there is none. `designation` is not indexed in
    `alerce_tap.lsst_mpc_orbits`, so this is slower than an ID lookup. Only designation
    characters are accepted, so the value can be quoted into ADQL safely.
    """
    designation = " ".join(designation.split())
    if not LSST_DESIGNATION_PATTERN.match(designation):
        raise QueryServiceError(f"{designation!r} is not an LSST object ID or asteroid designation")
    rows = tap_service.search(
        f"SELECT ssObjectId FROM alerce_tap.lsst_mpc_orbits WHERE designation = '{designation}'"
    )
    return int(rows[0]["ssobjectid"]) if len(rows) else None


ZTF_OID_PATTERN = re.compile(r"^ZTF\d{2}[a-z]{7}$")
# LSST diaObjectIds/ssObjectIds are 17-18 digits; shorter numbers are e.g. numbered asteroids like "6478"
LSST_OID_PATTERN = re.compile(r"^\d{15,}$")
TNS_NAME_PATTERN = re.compile(r"^(?:AT|SN)\s?(\d{4}[a-z]{1,3})$")
# Provisional ("1988 JC1"), survey ("2040 P-L") and comet ("C/2025 A6") designations; ALeRCE
# knows asteroids only by these, not by number or name
MPC_DESIGNATION_PATTERN = re.compile(r"^(?:[CPDXAI]/)?\d{4} (?:[A-Z]{1,2}\d*(?:-[A-Z])?|[PT]-[L123])$")


def _alerce_id_from_name(name: str) -> tuple[str, str] | None:
    """Returns (survey, oid) if `name` is itself a ZTF or LSST ALeRCE object ID."""
    if ZTF_OID_PATTERN.match(name):
        return "ZTF", name
    if LSST_OID_PATTERN.match(name):
        return "LSST", name
    return None


def _alerce_id_from_remote_name(name: str) -> tuple[str, str] | None:
    """
    Returns (survey, oid) for a TNS name (via the ZTF/LSST IDs in its TNS internal names)
    or an MPC designation (via `alerce_tap.lsst_mpc_orbits`), or None. Lookup failures,
    including TNS not being configured, are logged and give None, so a data update falls
    back to other names rather than failing.
    """
    if tns_match := TNS_NAME_PATTERN.match(name):
        for internal_name in _tns_internal_names(tns_match.group(1)):
            if found := _alerce_id_from_name(internal_name):
                return found
        return None
    if MPC_DESIGNATION_PATTERN.match(name):
        try:
            ss_object_id = _resolve_lsst_designation(name)
        except (pyvo.dal.DALAccessError, QueryServiceError):
            logger.exception(f"Error resolving MPC designation {name} with ALeRCE")
            return None
        return ("LSST", str(ss_object_id)) if ss_object_id is not None else None
    return None


def _tns_internal_names(objname: str) -> list[str]:
    """
    Returns the internal (survey) names TNS lists for an object, given its name without
    the AT/SN prefix, or [] if TNS isn't configured, has no such object, or fails.
    """
    tns = TNSDataService()
    try:
        data = tns.query_service(tns.build_query_parameters({"objname": objname}), url=tns.get_urls("object_url"))
    except NotConfiguredError:
        logger.info(f"TNS is not configured; cannot resolve {objname} to ALeRCE IDs")
        return []
    except (requests.RequestException, ValueError, KeyError):
        logger.exception(f"Error querying TNS for {objname}")
        return []
    if not isinstance(data, dict) or not data.get("objname"):
        return []
    return [name.strip() for name in (data.get("internal_names") or "").split(",") if name.strip()]


def _non_sidereal_target_from_mpc_orbit(name, orbit: dict) -> Target:
    """
    Builds a NON_SIDEREAL Target from an `alerce_tap.lsst_mpc_orbits` record. The table's
    `a`/`mean_anomaly`/`mean_motion` can be 0.0 placeholders rather than null, so, as in
    `MPCExplorerDataService.create_target_from_query`, they are derived from the
    always-present perihelion elements (`q`, `e`, `peri_time`). Bound orbits (e < 1) use
    the MPC_MINOR_PLANET scheme; unbound ones use MPC_COMET.
    """
    target = Target(
        name=name,
        type=Target.NON_SIDEREAL,
        scheme="MPC_COMET",
        epoch_of_elements=orbit["epoch_mjd"],
        inclination=orbit["i"],
        lng_asc_node=orbit["node"],
        arg_of_perihelion=orbit["argperi"],
        eccentricity=orbit["e"],
        perihdist=orbit["q"],
        epoch_of_perihelion=orbit["peri_time"],
        abs_mag=orbit.get("h"),
        slope=orbit.get("g"),
    )
    if target.eccentricity < 1.0:
        target.scheme = "MPC_MINOR_PLANET"
        target.semimajor_axis = target.perihdist / (1.0 - target.eccentricity)
        target.mean_daily_motion = GAUSSIAN_K_DEG_PER_DAY / target.semimajor_axis ** 1.5
        target.mean_anomaly = (
            (target.epoch_of_elements - target.epoch_of_perihelion) * target.mean_daily_motion
        ) % 360.0
    return target


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
    object_id = forms.CharField(
        required=False, label="Object ID",
        help_text="For LSST, a diaObjectId, an ssObjectId, or an asteroid designation such as 2010 WX64.",
    )
    ra = forms.FloatField(required=False, label="RA (deg)")
    dec = forms.FloatField(required=False, label="Dec (deg)")
    radius = forms.FloatField(required=False, label="Search Radius (arcsec)")
    firstmjd_gt = forms.FloatField(required=False, label="Min MJD of first detection")
    firstmjd_lt = forms.FloatField(required=False, label="Max MJD of first detection")
    lastmjd_gt = forms.FloatField(required=False, label="Min MJD of last detection")
    lastmjd_lt = forms.FloatField(required=False, label="Max MJD of last detection")
    ndet_min = forms.IntegerField(required=False, label="Min. Number of Detections")
    ndet_max = forms.IntegerField(required=False, label="Max Number of Detections")
    deltamjd_max = forms.FloatField(
        required=False, label="Max. Detection Time Span (days)", min_value=0,
        help_text="LSST only. Time between first and last detection. Less than 1 day, combined with the stamp "
                  "classifier's asteroid class, finds candidate new moving objects.",
    )
    max_results = forms.IntegerField(
        required=False, label="Max. Results", initial=DEFAULT_PAGE_SIZE, min_value=1, max_value=MAX_PAGE_SIZE,
        help_text="Per classifier, when filtering by classifier.",
    )
    order_by = forms.ChoiceField(
        required=False, label="Sort By",
        choices=[("", "Default"), ("lastmjd", "Last detection"), ("firstmjd", "First detection"),
                 ("ndet", "Number of detections")],
        help_text="Default is by probability for LSST classifier searches.",
    )
    order_mode = forms.ChoiceField(
        required=False, label="Sort Order", choices=[("DESC", "Descending"), ("ASC", "Ascending")], initial="DESC",
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Dynamically add the classifier fields to the form
        self.add_classifiers_fields()
        # Make the survey field hidden for now until the LSST API is more featured
        # self.fields['survey'].widget = forms.HiddenInput()

    def get_classifiers(self, survey: str) -> list[dict]:
        """
        Returns the survey's classifiers, or none if the TAP query fails, so the form still
        renders (without classifier fields) during an ALeRCE TAP outage. The failure is not
        cached, so the next form load retries.
        """
        tid = SURVEY_TID.get(survey, SURVEY_TID["ZTF"])
        try:
            return _fetch_classifiers_for_tid(tid)
        except pyvo.dal.DALAccessError:
            logger.exception(f"Error querying ALeRCE {survey} classifiers")
            return []

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

        # The ZTF REST API has no deltajd filter
        if cleaned_data.get("deltamjd_max") is not None and selected_survey != "LSST":
            self.add_error("deltamjd_max", "Only supported for LSST searches.")

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
                    items = alerce.query_objects(**query_parameters).get("items", [])
                    results = [_normalize_ztf_record(item) for item in items]
                else:
                    oid = str(query_parameters["oid"]).strip()
                    if not oid.isdigit():
                        oid, sid = _resolve_lsst_designation(oid), 2
                    if oid is not None:
                        query = '''
                            SELECT * FROM alerce_tap.object
                            WHERE oid = %s AND sid = %d
                            ''' % (int(oid), sid)
                        results = [_normalize_tap_record(dict(row)) for row in tap_service.search(query)]

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
                        # The query filters by class_id; add the names, as ZTF REST results carry them
                        results.extend(
                            {**_normalize_tap_record(dict(row)),
                             "class": classifier["class"], "classifier": classifier["classifier"]}
                            for row in tap_service.search(tap_query)
                        )
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
        except pyvo.dal.DALAccessError as e:
            logger.exception("Error querying the ALeRCE TAP service")
            raise QueryServiceError(f"ALeRCE TAP query failed: {e}")

        for result in results:
            result["survey"] = query_parameters["survey"]
            result["alerce_url"] = ALERCE_EXPLORER_URLS[result["survey"]].format(oid=result["oid"])

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

        if survey == "LSST" and form_parameters.get("deltamjd_max") is not None:
            query_params["deltamjd_max"] = form_parameters["deltamjd_max"]

        if max_results := form_parameters.get("max_results"):
            query_params["page_size"] = max_results
        if order_by := form_parameters.get("order_by"):
            query_params["order_by"] = order_by
            query_params["order_mode"] = form_parameters.get("order_mode") or "DESC"

        if form_parameters.get("object_id"):
            query_params["oid"] = form_parameters.get("object_id")
        query_params["classifiers"] = form_parameters.get("classifiers", [])
        return query_params

    def build_query_parameters_from_target(self, target, **kwargs):
        """
        Finds the ALeRCE object for a target from its name or aliases, so data can be
        updated for targets created elsewhere (e.g. named by TNS or the MPC) that carry a
        ZTF or LSST ID, a TNS name or an MPC designation among their names. Names that are
        already ALeRCE IDs are tried first, so no remote lookup happens when one exists;
        then TNS names and MPC designations are resolved remotely, in the same name-then-
        alias order. If nothing resolves, the target's name is used as before.
        """
        names = [str(target.name)] + [str(alias) for alias in target.aliases.values_list("name", flat=True)]
        for resolve in (_alerce_id_from_name, _alerce_id_from_remote_name):
            for name in names:
                if found := resolve(name):
                    survey, object_id = found
                    return {"object_id": object_id, "survey": survey}
        return {"object_id": str(target.name), "survey": "ZTF" if str(target.name).startswith("ZTF") else "LSST"}

    def create_target_from_query(self, target_result: dict, **kwrags):
        """
        LSST ssObjects (sid=2) become NON_SIDEREAL targets built from their
        `alerce_tap.lsst_mpc_orbits` elements. If no orbit is stored, or the TAP query
        fails, the target falls back to SIDEREAL at the object's mean position, since
        that's better than failing target creation. Everything else is SIDEREAL.
        """
        # LSST oids come back from TAP as integers; the Target must hold the string the DB will
        # store, since code after to_target() uses the unsaved-then-saved instance directly.
        name = str(target_result["oid"])
        if target_result.get("sid") == 2:
            try:
                orbit = _fetch_lsst_mpc_orbit(target_result["oid"])
            except pyvo.dal.DALAccessError:
                logger.exception(f"Error querying ALeRCE MPC orbit for ssObject {name}")
                orbit = None
            if orbit:
                return _non_sidereal_target_from_mpc_orbit(name, orbit)
            logger.warning(f"No ALeRCE MPC orbit for ssObject {name}; creating a SIDEREAL target")
        target = Target(
            name=name,
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

    def query_aliases(self, query_parameters=None, target=None, **kwargs) -> list:
        """
        Returns the MPC designation (e.g. "2020 TE16") of a non-sidereal target named by
        its LSST ssObjectId, so it can be found by its familiar name. The target keeps the
        ssObjectId as its name, since `build_query_parameters_from_target` uses the name
        to look up photometry. Other targets have no ALeRCE aliases. A TAP failure is
        logged and yields no aliases rather than failing target creation or data update.
        """
        if target is None or target.type != Target.NON_SIDEREAL or not str(target.name).isdigit():
            return []
        try:
            orbit = _fetch_lsst_mpc_orbit(target.name)
        except pyvo.dal.DALAccessError:
            logger.exception(f"Error querying ALeRCE MPC designation for {target.name}")
            return []
        designation = orbit.get("designation") if orbit else None
        return [designation] if designation else []

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
        """
        Creates PhotometryReducedDatums from an ALeRCE light curve. Detections in the
        LSST shape (`psfFlux` in nJy, integer `band`, TAI `mjd`) are converted to AB
        magnitudes via `_lsst_detection_photometry`; ZTF detections (`magpsf`, `fid`)
        and non-detections are stored as-is. LSST detections with non-positive
        difference flux have no magnitude and are skipped.
        """
        reduced_datums = []
        if data:
            for detection in data.get("detections", []):
                if "psfFlux" in detection:
                    photometry = _lsst_detection_photometry(detection)
                    if photometry is None:
                        continue
                    mjd = Time(detection["mjd"], format="mjd", scale="tai").utc
                else:
                    photometry = {
                        "brightness": detection["magpsf"],
                        "brightness_error": detection["sigmapsf"],
                        "bandpass": ALERCE_FILTERS[detection["fid"]],
                    }
                    mjd = Time(detection["mjd"], format="mjd", scale="utc")
                try:
                    reduced_datum, __ = PhotometryReducedDatum.objects.get_or_create(
                        timestamp=mjd.to_datetime(TimezoneInfo()),
                        target=target,
                        unit='mag',
                        defaults={'source_name': self.name},
                        **photometry,
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
