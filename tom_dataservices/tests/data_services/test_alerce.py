import unittest
from unittest.mock import patch

from alerce.exceptions import APIError, ObjectNotFoundError
from django.core.cache import cache
from django.test import TestCase

import numpy as np

from tom_dataservices.data_services.alerce import (
    AlerceDataService,
    AlerceForm,
    _build_tap_object_query,
    _group_tap_classifier_rows,
)
from tom_dataservices.dataservices import QueryServiceError
from tom_targets.models import Target

MOCK_CLASSIFIERS = [
    {
        "classifier_name": "lc_classifier",
        "classifier_version": "hierarchical_random_forest_1.0.0",
        "classes": ["SNIa", "SNII", "AGN"],
    },
    {
        "classifier_name": "stamp_classifier",
        "classifier_version": "stamp_classifier_1.0.1",
        "classes": ["AGN", "SN", "bogus"],
    },
]

# alerce_tap.classifier JOIN alerce_tap.taxonomy rows (tid=0, ZTF) that group into MOCK_CLASSIFIERS
MOCK_ZTF_TAP_CLASSIFIER_ROWS = [
    {"classifier_name": "lc_classifier", "classifier_version": "hierarchical_random_forest_1.0.0",
     "class_name": "SNIa"},
    {"classifier_name": "lc_classifier", "classifier_version": "hierarchical_random_forest_1.0.0",
     "class_name": "SNII"},
    {"classifier_name": "lc_classifier", "classifier_version": "hierarchical_random_forest_1.0.0",
     "class_name": "AGN"},
    {"classifier_name": "stamp_classifier", "classifier_version": "stamp_classifier_1.0.1", "class_name": "AGN"},
    {"classifier_name": "stamp_classifier", "classifier_version": "stamp_classifier_1.0.1", "class_name": "SN"},
    {"classifier_name": "stamp_classifier", "classifier_version": "stamp_classifier_1.0.1", "class_name": "bogus"},
]

# tid=1 (LSST) rows, exercising the LSST-only stamp classifier
MOCK_LSST_TAP_CLASSIFIER_ROWS = [
    {"classifier_name": "stamp_classifier_rubin_beta", "classifier_version": "1.0.0", "class_name": "SN"},
    {"classifier_name": "stamp_classifier_rubin_beta", "classifier_version": "1.0.0", "class_name": "bogus"},
]


class TestAlerceForm(TestCase):
    def setUp(self):
        cache.clear()
        alerce_patcher = patch("tom_dataservices.data_services.alerce.alerce")
        self.mock_alerce = alerce_patcher.start()
        self.addCleanup(alerce_patcher.stop)
        tap_patcher = patch("tom_dataservices.data_services.alerce.tap_service")
        self.mock_tap_service = tap_patcher.start()
        self.addCleanup(tap_patcher.stop)
        self.mock_tap_service.search.return_value = MOCK_ZTF_TAP_CLASSIFIER_ROWS

    def test_classifier_fields_added_dynamically(self):
        form = AlerceForm(data={"data_service": "ALeRCE"})
        self.assertIn("cfield_lc_classifier", form.fields)
        self.assertIn("prob_cfield_lc_classifier", form.fields)
        self.assertEqual(
            form.fields["cfield_lc_classifier"].choices,
            [(None, "")] + [(k, k) for k in ["SNIa", "SNII", "AGN"]],
        )
        self.assertIn("cfield_stamp_classifier", form.fields)

    def test_classifiers_cached_after_first_query(self):
        AlerceForm(data={"data_service": "ALeRCE"})
        AlerceForm(data={"data_service": "ALeRCE"})
        self.mock_tap_service.search.assert_called_once()

    def test_get_classifiers_query_uses_tid_for_survey(self):
        AlerceForm(data={"data_service": "ALeRCE", "survey": "LSST"})
        adql = self.mock_tap_service.search.call_args.args[0]
        self.assertIn("c.tid = 1", adql)

        cache.clear()
        AlerceForm(data={"data_service": "ALeRCE", "survey": "ZTF"})
        adql = self.mock_tap_service.search.call_args.args[0]
        self.assertIn("c.tid = 0", adql)

    def test_per_survey_cache_keys_query_tap_independently(self):
        AlerceForm(data={"data_service": "ALeRCE", "survey": "ZTF"})
        AlerceForm(data={"data_service": "ALeRCE", "survey": "LSST"})
        self.assertEqual(self.mock_tap_service.search.call_count, 2)
        # Re-instantiating either survey's form now hits the per-survey cache.
        AlerceForm(data={"data_service": "ALeRCE", "survey": "ZTF"})
        AlerceForm(data={"data_service": "ALeRCE", "survey": "LSST"})
        self.assertEqual(self.mock_tap_service.search.call_count, 2)

    def test_lsst_form_gets_lsst_classifier_entries(self):
        self.mock_tap_service.search.return_value = MOCK_LSST_TAP_CLASSIFIER_ROWS
        form = AlerceForm(data={"data_service": "ALeRCE", "survey": "LSST"})
        self.assertIn("cfield_stamp_classifier_rubin_beta", form.fields)
        self.assertEqual(
            form.fields["cfield_stamp_classifier_rubin_beta"].choices,
            [(None, "")] + [(k, k) for k in ["SN", "bogus"]],
        )

    def test_no_rest_query_classifiers_call(self):
        AlerceForm(data={"data_service": "ALeRCE"})
        self.mock_alerce.query_classifiers.assert_not_called()

    def test_clean_bundles_selected_classifiers(self):
        form = AlerceForm(
            data={
                "data_service": "ALeRCE",
                "survey": "ZTF",
                "cfield_lc_classifier": "SNIa",
                "prob_cfield_lc_classifier": 0.8,
            }
        )
        self.assertTrue(form.is_valid(), form.errors)
        self.assertEqual(
            form.cleaned_data["classifiers"],
            [{"classifier": "lc_classifier", "class": "SNIa", "probability": 0.8}],
        )


class TestGroupTapClassifierRows(TestCase):
    def test_groups_by_classifier_name_and_version_preserving_taxonomy_order(self):
        grouped = _group_tap_classifier_rows(MOCK_ZTF_TAP_CLASSIFIER_ROWS)
        self.assertEqual(grouped, MOCK_CLASSIFIERS)

    def test_empty_rows_returns_empty_list(self):
        self.assertEqual(_group_tap_classifier_rows([]), [])


class TestBuildQueryParameters(TestCase):
    def setUp(self):
        self.ds = AlerceDataService()

    def test_ztf_survey_sid_and_name(self):
        params = self.ds.build_query_parameters({"survey": "ZTF"})
        self.assertEqual(params["sid"], 0)
        self.assertEqual(params["survey"], "ztf")

    def test_lsst_diaobject_sid(self):
        params = self.ds.build_query_parameters({"survey": "LSST", "lsst_object_type": "diaObject"})
        self.assertEqual(params["sid"], 1)

    def test_lsst_ssobject_sid(self):
        params = self.ds.build_query_parameters({"survey": "LSST", "lsst_object_type": "ssObject"})
        self.assertEqual(params["sid"], 2)

    def test_firstmjd_lastmjd_only_set_when_both_bounds_given(self):
        params = self.ds.build_query_parameters(
            {"survey": "ZTF", "firstmjd_gt": 59000.0, "firstmjd_lt": 59500.0}
        )
        self.assertEqual(params["firstmjd"], [59000.0, 59500.0])
        self.assertNotIn("lastmjd", params)

        params = self.ds.build_query_parameters({"survey": "ZTF", "firstmjd_gt": 59000.0})
        self.assertNotIn("firstmjd", params)

    def test_ndet_min_and_max(self):
        params = self.ds.build_query_parameters({"survey": "ZTF", "ndet_min": 3, "ndet_max": 10})
        self.assertEqual(params["ndet"], [3, 10])

    def test_ndet_max_only_defaults_min_to_zero(self):
        params = self.ds.build_query_parameters({"survey": "ZTF", "ndet_max": 10})
        self.assertEqual(params["ndet"], [0, 10])

    def test_ndet_min_only(self):
        params = self.ds.build_query_parameters({"survey": "ZTF", "ndet_min": 3})
        self.assertEqual(params["ndet"], [3])

    def test_ndet_absent_when_neither_given(self):
        params = self.ds.build_query_parameters({"survey": "ZTF"})
        self.assertNotIn("ndet", params)

    def test_cone_params_set_only_when_all_present(self):
        params = self.ds.build_query_parameters(
            {"survey": "ZTF", "ra": 10.0, "dec": 20.0, "radius": 30.0}
        )
        self.assertEqual(params["ra"], 10.0)
        self.assertEqual(params["dec"], 20.0)
        self.assertEqual(params["radius"], 30.0)

        params = self.ds.build_query_parameters({"survey": "ZTF", "ra": 10.0, "dec": 20.0})
        self.assertNotIn("ra", params)

    def test_object_id_becomes_oid(self):
        params = self.ds.build_query_parameters({"survey": "ZTF", "object_id": "ZTF18aaaaaa"})
        self.assertEqual(params["oid"], "ZTF18aaaaaa")

    def test_classifiers_defaults_to_empty_list(self):
        params = self.ds.build_query_parameters({"survey": "ZTF"})
        self.assertEqual(params["classifiers"], [])


class TestBuildTapObjectQuery(TestCase):
    def test_top_and_sid(self):
        query = _build_tap_object_query({"sid": 1})
        self.assertIn("SELECT TOP 20 * FROM alerce_tap.object", query)
        self.assertIn("WHERE sid = 1", query)

    def test_page_size_override(self):
        query = _build_tap_object_query({"sid": 2}, page_size=50)
        self.assertIn("SELECT TOP 50", query)

    def test_cone_search_converts_radius_arcsec_to_degrees(self):
        query = _build_tap_object_query({"sid": 1, "ra": 305.58, "dec": -18.79, "radius": 3600.0})
        self.assertIn(
            "CONTAINS(POINT('ICRS', meanra, meandec), CIRCLE('ICRS', 305.58, -18.79, 1.0))",
            query,
        )

    def test_cone_search_absent_when_any_param_missing(self):
        query = _build_tap_object_query({"sid": 1, "ra": 305.58, "dec": -18.79})
        self.assertNotIn("CONTAINS", query)

    def test_mjd_ranges(self):
        query = _build_tap_object_query({"sid": 1, "firstmjd": [59000.0, 59500.0], "lastmjd": [59100.0, 59600.0]})
        self.assertIn("AND firstmjd >= 59000.0 AND firstmjd <= 59500.0", query)
        self.assertIn("AND lastmjd >= 59100.0 AND lastmjd <= 59600.0", query)

    def test_ndet_two_sided(self):
        query = _build_tap_object_query({"sid": 1, "ndet": [3, 10]})
        self.assertIn("AND n_det >= 3", query)
        self.assertIn("AND n_det <= 10", query)

    def test_ndet_one_sided(self):
        query = _build_tap_object_query({"sid": 1, "ndet": [3]})
        self.assertIn("AND n_det >= 3", query)
        self.assertNotIn("n_det <=", query)


class TestQueryService(TestCase):
    def setUp(self):
        self.ds = AlerceDataService()
        alerce_patcher = patch("tom_dataservices.data_services.alerce.alerce")
        self.mock_alerce = alerce_patcher.start()
        self.addCleanup(alerce_patcher.stop)
        tap_patcher = patch("tom_dataservices.data_services.alerce.tap_service")
        self.mock_tap_service = tap_patcher.start()
        self.addCleanup(tap_patcher.stop)

    def test_ztf_oid_path_uses_rest_and_strips_sid(self):
        self.mock_alerce.query_objects.return_value = {"oid": "ZTF18aaaaaa", "meanra": 10.0}
        result = self.ds.query_service({"oid": "ZTF18aaaaaa", "sid": 0, "survey": "ztf"})
        self.mock_alerce.query_objects.assert_called_once()
        call_kwargs = self.mock_alerce.query_objects.call_args.kwargs
        self.assertNotIn("sid", call_kwargs)
        self.assertEqual(result, [{"oid": "ZTF18aaaaaa", "meanra": 10.0}])

    def test_lsst_oid_path_uses_tap_and_renames_ndet(self):
        row = {
            "oid": 12345,
            "meanra": np.float64(10.0),
            "meandec": np.float64(-5.0),
            "n_det": np.int64(7),
        }
        self.mock_tap_service.search.return_value = [row]
        result = self.ds.query_service({"oid": 12345, "sid": 1, "survey": "lsst"})

        adql = self.mock_tap_service.search.call_args.args[0]
        self.assertIn("oid =", adql)
        self.assertIn("sid = 1", adql)
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["ndet"], 7)
        self.assertNotIn("n_det", result[0])
        self.assertIsInstance(result[0]["ndet"], int)
        self.assertIsInstance(result[0]["meanra"], float)

    def test_ztf_general_query_unwraps_items_and_annotates_survey(self):
        self.mock_alerce.query_objects.return_value = {
            "items": [{"oid": "ZTF18aaaaaa"}, {"oid": "ZTF18bbbbbb"}]
        }
        result = self.ds.query_service({"sid": 0, "survey": "ztf", "classifiers": []})
        self.assertEqual(len(result), 2)
        self.assertTrue(all(r["survey"] == "ztf" for r in result))

    def test_ztf_classifier_loop_queries_once_per_classifier(self):
        self.mock_alerce.query_objects.return_value = {"items": [{"oid": "ZTF18aaaaaa"}]}
        classifiers = [
            {"classifier": "lc_classifier", "class": "SNIa", "probability": 0.5},
            {"classifier": "stamp_classifier", "class": "AGN", "probability": 0.9},
        ]
        result = self.ds.query_service(
            {"sid": 0, "survey": "ztf", "classifiers": classifiers}
        )
        self.assertEqual(self.mock_alerce.query_objects.call_count, 2)
        first_call_kwargs = self.mock_alerce.query_objects.call_args_list[0].kwargs
        self.assertEqual(first_call_kwargs["classifier"], "lc_classifier")
        self.assertEqual(first_call_kwargs["class_name"], "SNIa")
        self.assertEqual(first_call_kwargs["probability"], 0.5)
        self.assertEqual(len(result), 2)

    def test_object_not_found_error_raises_query_service_error(self):
        self.mock_alerce.query_objects.side_effect = ObjectNotFoundError("nope")
        with self.assertRaises(QueryServiceError):
            self.ds.query_service({"sid": 0, "survey": "ztf", "classifiers": []})

    def test_api_error_raises_query_service_error(self):
        self.mock_alerce.query_objects.side_effect = APIError("boom")
        with self.assertRaises(QueryServiceError):
            self.ds.query_service({"sid": 0, "survey": "ztf", "classifiers": []})

    def test_value_error_raises_query_service_error(self):
        self.mock_alerce.query_objects.side_effect = ValueError("bad param")
        with self.assertRaises(QueryServiceError):
            self.ds.query_service({"sid": 0, "survey": "ztf", "classifiers": []})

    def test_lsst_general_query_returns_annotated_results(self):
        """
        LSST general (non-oid) queries now go through TAP against alerce_tap.object
        instead of the REST client (whose query_objects(survey='lsst') returns a
        bare list, breaking the ZTF-shaped `.get("items", [])` unwrap).
        """
        rows = [
            {"oid": 12345, "meanra": np.float64(10.0), "n_det": np.int64(5)},
            {"oid": 67890, "meanra": np.float64(20.0), "n_det": np.int64(9)},
        ]
        self.mock_tap_service.search.return_value = rows
        result = self.ds.query_service({"sid": 1, "survey": "lsst", "classifiers": []})
        self.mock_tap_service.search.assert_called_once()
        self.assertEqual(len(result), 2)
        self.assertTrue(all(r["survey"] == "lsst" for r in result))
        self.assertEqual(result[0]["ndet"], 5)
        self.assertNotIn("n_det", result[0])

    def test_lsst_classifier_general_query_raises_query_service_error(self):
        classifiers = [{"classifier": "lc_classifier", "class": "SNIa", "probability": 0.5}]
        with self.assertRaises(QueryServiceError):
            self.ds.query_service({"sid": 1, "survey": "lsst", "classifiers": classifiers})
        self.mock_tap_service.search.assert_not_called()

    def test_ztf_general_query_normalizes_deltajd_to_deltamjd(self):
        self.mock_alerce.query_objects.return_value = {
            "items": [{"oid": "ZTF18aaaaaa", "deltajd": 12.5}]
        }
        result = self.ds.query_service({"sid": 0, "survey": "ztf", "classifiers": []})
        self.assertEqual(result[0]["deltamjd"], 12.5)
        self.assertNotIn("deltajd", result[0])


class TestTargetAndDatumCreation(TestCase):
    def setUp(self):
        self.ds = AlerceDataService()

    def test_create_target_from_query(self):
        target = self.ds.create_target_from_query(
            {"oid": "ZTF18aaaaaa", "meanra": 10.0, "meandec": -5.0}
        )
        self.assertEqual(target.name, "ZTF18aaaaaa")
        self.assertEqual(target.type, "SIDEREAL")
        self.assertEqual(target.ra, 10.0)
        self.assertEqual(target.dec, -5.0)

    def test_create_target_extras_from_query_excludes_core_fields(self):
        extras = self.ds.create_target_extras_from_query(
            {"oid": "ZTF18aaaaaa", "meanra": 10.0, "meandec": -5.0, "ndet": 7, "survey": "ztf"}
        )
        self.assertNotIn("oid", extras)
        self.assertNotIn("meanra", extras)
        self.assertNotIn("meandec", extras)
        self.assertEqual(extras, {"ndet": 7, "survey": "ztf"})

    def test_create_reduced_datums_from_ztf_detections_and_non_detections(self):
        target = Target.objects.create(name="ZTF18aaaaaa", type="SIDEREAL", ra=10.0, dec=-5.0)
        data = {
            "detections": [
                {"mjd": 59000.0, "magpsf": 18.5, "sigmapsf": 0.1, "fid": 1},
            ],
            "non_detections": [
                {"mjd": 58999.0, "diffmaglim": 20.0, "fid": 2},
            ],
        }
        reduced_datums = self.ds.create_reduced_datums_from_query(target, data=data)
        self.assertEqual(len(reduced_datums), 2)

    @unittest.expectedFailure
    def test_lsst_detection_fixture_creates_reduced_datum(self):
        """
        LSST detections carry flux (`psfFlux`) and an integer `band`, not the
        ZTF REST shape's `magpsf`/`sigmapsf`/`fid`. create_reduced_datums_from_query
        assumes the ZTF shape unconditionally, so an LSST detection raises
        KeyError. Documents the flux-vs-mag gap left out of scope for this
        migration (see design doc "Out of scope").
        """
        target = Target.objects.create(name="LSST12345", type="SIDEREAL", ra=10.0, dec=-5.0)
        data = {
            "detections": [
                {"mjd": 59000.0, "psfFlux": 123.4, "band": 4},
            ],
            "non_detections": [],
        }
        reduced_datums = self.ds.create_reduced_datums_from_query(target, data=data)
        self.assertEqual(len(reduced_datums), 1)
