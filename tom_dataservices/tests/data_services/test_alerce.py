import math
from unittest.mock import patch

from alerce.exceptions import APIError, ObjectNotFoundError
from astropy.time import Time, TimezoneInfo
from django.core.cache import cache
from django.template.loader import render_to_string
from django.test import TestCase

import numpy as np

from tom_dataservices.data_services.alerce import (
    AlerceDataService,
    AlerceForm,
    _build_tap_classifier_query,
    _build_tap_object_query,
    _group_tap_classifier_rows,
)
from tom_dataservices.dataservices import QueryServiceError
from tom_targets.models import Target

MOCK_CLASSIFIERS = [
    {
        "classifier_id": 10,
        "classifier_name": "lc_classifier",
        "classifier_version": "hierarchical_random_forest_1.0.0",
        "classes": ["SNIa", "SNII", "AGN"],
        "class_ids": {"SNIa": 0, "SNII": 1, "AGN": 2},
    },
    {
        "classifier_id": 11,
        "classifier_name": "stamp_classifier",
        "classifier_version": "stamp_classifier_1.0.1",
        "classes": ["AGN", "SN", "bogus"],
        "class_ids": {"AGN": 0, "SN": 1, "bogus": 2},
    },
]

# alerce_tap.classifier JOIN alerce_tap.taxonomy rows (tid=0, ZTF) that group into MOCK_CLASSIFIERS
MOCK_ZTF_TAP_CLASSIFIER_ROWS = [
    {"classifier_id": 10, "classifier_name": "lc_classifier",
     "classifier_version": "hierarchical_random_forest_1.0.0", "class_id": 0, "class_name": "SNIa"},
    {"classifier_id": 10, "classifier_name": "lc_classifier",
     "classifier_version": "hierarchical_random_forest_1.0.0", "class_id": 1, "class_name": "SNII"},
    {"classifier_id": 10, "classifier_name": "lc_classifier",
     "classifier_version": "hierarchical_random_forest_1.0.0", "class_id": 2, "class_name": "AGN"},
    {"classifier_id": 11, "classifier_name": "stamp_classifier", "classifier_version": "stamp_classifier_1.0.1",
     "class_id": 0, "class_name": "AGN"},
    {"classifier_id": 11, "classifier_name": "stamp_classifier", "classifier_version": "stamp_classifier_1.0.1",
     "class_id": 1, "class_name": "SN"},
    {"classifier_id": 11, "classifier_name": "stamp_classifier", "classifier_version": "stamp_classifier_1.0.1",
     "class_id": 2, "class_name": "bogus"},
]

# tid=1 (LSST) rows, exercising the LSST-only stamp classifier
MOCK_LSST_TAP_CLASSIFIER_ROWS = [
    {"classifier_id": 20, "classifier_name": "stamp_classifier_rubin_beta", "classifier_version": "1.0.0",
     "class_id": 3, "class_name": "SN"},
    {"classifier_id": 20, "classifier_name": "stamp_classifier_rubin_beta", "classifier_version": "1.0.0",
     "class_id": 4, "class_name": "bogus"},
]


def _tap_classifier_side_effect(ztf_rows=None, lsst_rows=None):
    """
    add_classifiers_fields() now queries TAP once per survey (so every survey's
    classifier fields are always on the form -- see its docstring). Route each
    tap_service.search() call's mocked response by the `tid` filter in the ADQL query,
    rather than a single fixed return_value, so ZTF (tid=0) and LSST (tid=1) get their
    own rows regardless of call order.
    """
    ztf_rows = MOCK_ZTF_TAP_CLASSIFIER_ROWS if ztf_rows is None else ztf_rows
    lsst_rows = MOCK_LSST_TAP_CLASSIFIER_ROWS if lsst_rows is None else lsst_rows

    def _search(query, *args, **kwargs):
        return lsst_rows if "tid = 1" in query else ztf_rows

    return _search


class TestAlerceForm(TestCase):
    def setUp(self):
        cache.clear()
        alerce_patcher = patch("tom_dataservices.data_services.alerce.alerce")
        self.mock_alerce = alerce_patcher.start()
        self.addCleanup(alerce_patcher.stop)
        tap_patcher = patch("tom_dataservices.data_services.alerce.tap_service")
        self.mock_tap_service = tap_patcher.start()
        self.addCleanup(tap_patcher.stop)
        self.mock_tap_service.search.side_effect = _tap_classifier_side_effect()

    def test_ztf_classifier_fields_added_dynamically(self):
        form = AlerceForm(data={"data_service": "ALeRCE"})
        self.assertIn("cfield_ZTF__lc_classifier", form.fields)
        self.assertIn("prob_cfield_ZTF__lc_classifier", form.fields)
        self.assertEqual(
            form.fields["cfield_ZTF__lc_classifier"].choices,
            [(None, "")] + [(k, k) for k in ["SNIa", "SNII", "AGN"]],
        )
        self.assertIn("cfield_ZTF__stamp_classifier", form.fields)

    def test_lsst_classifier_fields_added_dynamically(self):
        form = AlerceForm(data={"data_service": "ALeRCE"})
        self.assertIn("cfield_LSST__stamp_classifier_rubin_beta", form.fields)
        self.assertEqual(
            form.fields["cfield_LSST__stamp_classifier_rubin_beta"].choices,
            [(None, "")] + [(k, k) for k in ["SN", "bogus"]],
        )

    def test_both_surveys_classifier_fields_present_regardless_of_selection(self):
        """
        Every survey's classifier fields must be on the form regardless of which
        survey is currently selected, so the advanced form partial can show/hide the
        right set purely client-side (via Alpine, keyed off $store.alerce.survey) when
        the user switches surveys -- with no full form re-render.
        """
        form = AlerceForm(data={"data_service": "ALeRCE", "survey": "ZTF"})
        self.assertIn("cfield_ZTF__lc_classifier", form.fields)
        self.assertIn("cfield_LSST__stamp_classifier_rubin_beta", form.fields)

    def test_classifiers_cached_after_first_query(self):
        AlerceForm(data={"data_service": "ALeRCE"})
        self.assertEqual(self.mock_tap_service.search.call_count, 2)  # one per survey
        AlerceForm(data={"data_service": "ALeRCE"})
        self.assertEqual(self.mock_tap_service.search.call_count, 2)  # served from cache

    def test_get_classifiers_queries_use_tid_per_survey(self):
        AlerceForm(data={"data_service": "ALeRCE"})
        queries = [call.args[0] for call in self.mock_tap_service.search.call_args_list]
        self.assertTrue(any("c.tid = 0" in q for q in queries))
        self.assertTrue(any("c.tid = 1" in q for q in queries))

    def test_per_survey_cache_keys_are_independent(self):
        AlerceForm(data={"data_service": "ALeRCE"})
        self.assertIsNotNone(cache.get("ds_alerce_classifiers_0"))
        self.assertIsNotNone(cache.get("ds_alerce_classifiers_1"))

    def test_no_rest_query_classifiers_call(self):
        AlerceForm(data={"data_service": "ALeRCE"})
        self.mock_alerce.query_classifiers.assert_not_called()

    def test_clean_bundles_selected_classifiers_for_selected_survey(self):
        form = AlerceForm(
            data={
                "data_service": "ALeRCE",
                "survey": "ZTF",
                "cfield_ZTF__lc_classifier": "SNIa",
                "prob_cfield_ZTF__lc_classifier": 0.8,
            }
        )
        self.assertTrue(form.is_valid(), form.errors)
        self.assertEqual(
            form.cleaned_data["classifiers"],
            [{"classifier": "lc_classifier", "class": "SNIa", "probability": 0.8}],
        )

    def test_clean_ignores_stale_hidden_survey_classifier_value(self):
        """
        Regression test for what the client-side-only survey toggle makes possible: a
        user picks a ZTF classifier, then switches the Survey dropdown to LSST (no page
        reload, so the ZTF field's value is untouched) and submits. The ZTF field is
        hidden but still present (and still POSTed); clean() must not bundle it since it
        doesn't belong to the now-selected survey.
        """
        form = AlerceForm(
            data={
                "data_service": "ALeRCE",
                "survey": "LSST",
                "cfield_ZTF__lc_classifier": "SNIa",
                "prob_cfield_ZTF__lc_classifier": 0.8,
            }
        )
        self.assertTrue(form.is_valid(), form.errors)
        self.assertEqual(form.cleaned_data["classifiers"], [])


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

    def test_lastmjd_gt_only_yields_open_ended_lower_bound(self):
        """
        Unlike firstmjd, lastmjd supports an open-ended lower bound (e.g. "last
        detected after X") -- a common recency filter, per ALeRCE's own LSST TAP
        queries notebook, which only bounds lastmjd from below.
        """
        params = self.ds.build_query_parameters({"survey": "ZTF", "lastmjd_gt": 59000.0})
        self.assertEqual(params["lastmjd"], [59000.0])

    def test_lastmjd_gt_and_lt_yields_closed_range(self):
        params = self.ds.build_query_parameters(
            {"survey": "ZTF", "lastmjd_gt": 59000.0, "lastmjd_lt": 59500.0}
        )
        self.assertEqual(params["lastmjd"], [59000.0, 59500.0])

    def test_lastmjd_absent_when_gt_not_given(self):
        params = self.ds.build_query_parameters({"survey": "ZTF", "lastmjd_lt": 59500.0})
        self.assertNotIn("lastmjd", params)

    def test_ndet_min_and_max(self):
        params = self.ds.build_query_parameters({"survey": "ZTF", "ndet_min": 3, "ndet_max": 10})
        self.assertEqual(params["ndet"], [3, 10])

    def test_ndet_max_only_defaults_min_to_zero(self):
        params = self.ds.build_query_parameters({"survey": "ZTF", "ndet_max": 10})
        self.assertEqual(params["ndet"], [0, 10])

    def test_ndet_min_only(self):
        params = self.ds.build_query_parameters({"survey": "ZTF", "ndet_min": 3})
        self.assertEqual(params["ndet"], [3])

    def test_max_results_and_order_become_page_size_and_order(self):
        params = self.ds.build_query_parameters(
            {"survey": "ZTF", "max_results": 50, "order_by": "lastmjd", "order_mode": "ASC"}
        )
        self.assertEqual(params["page_size"], 50)
        self.assertEqual(params["order_by"], "lastmjd")
        self.assertEqual(params["order_mode"], "ASC")

    def test_order_mode_defaults_to_desc_and_is_omitted_without_order_by(self):
        params = self.ds.build_query_parameters({"survey": "ZTF", "order_by": "ndet"})
        self.assertEqual(params["order_mode"], "DESC")
        params = self.ds.build_query_parameters({"survey": "ZTF", "order_mode": "ASC"})
        self.assertNotIn("order_by", params)
        self.assertNotIn("order_mode", params)
        self.assertNotIn("page_size", params)

    def test_form_rejects_out_of_range_max_results_and_unknown_order(self):
        with patch("tom_dataservices.data_services.alerce._fetch_classifiers_for_tid", return_value=[]):
            form = AlerceForm(data={"data_service": "ALeRCE", "survey": "ZTF", "max_results": 0,
                                    "order_by": "oid; DROP"})
            self.assertFalse(form.is_valid())
        self.assertIn("max_results", form.errors)
        self.assertIn("order_by", form.errors)

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

    def test_page_size_from_query_parameters(self):
        self.assertIn("SELECT TOP 75 ", _build_tap_object_query({"sid": 1, "page_size": 75}))
        self.assertIn("SELECT TOP 20 ", _build_tap_object_query({"sid": 1}))

    def test_order_by_maps_ndet_to_n_det(self):
        query = _build_tap_object_query({"sid": 1, "ndet": [3], "order_by": "ndet", "order_mode": "DESC"})
        self.assertTrue(query.endswith("AND n_det >= 3 ORDER BY n_det DESC"))

    def test_no_order_clause_by_default(self):
        self.assertNotIn("ORDER BY", _build_tap_object_query({"sid": 1}))

    def test_unknown_order_column_and_mode_not_interpolated(self):
        query = _build_tap_object_query({"sid": 1, "order_by": "oid; DROP TABLE x", "order_mode": "ASC"})
        self.assertNotIn("ORDER BY", query)
        query = _build_tap_object_query({"sid": 1, "order_by": "lastmjd", "order_mode": "ASC; --"})
        self.assertTrue(query.endswith("ORDER BY lastmjd DESC"))

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

    def test_lastmjd_one_sided(self):
        query = _build_tap_object_query({"sid": 1, "lastmjd": [59100.0]})
        self.assertIn("AND lastmjd >= 59100.0", query)
        self.assertNotIn("lastmjd <=", query)

    def test_ndet_two_sided(self):
        query = _build_tap_object_query({"sid": 1, "ndet": [3, 10]})
        self.assertIn("AND n_det >= 3", query)
        self.assertIn("AND n_det <= 10", query)

    def test_ndet_one_sided(self):
        query = _build_tap_object_query({"sid": 1, "ndet": [3]})
        self.assertIn("AND n_det >= 3", query)
        self.assertNotIn("n_det <=", query)


class TestBuildTapClassifierQuery(TestCase):
    def test_joins_object_and_probability_filtered_by_ids_and_ranking(self):
        query = _build_tap_classifier_query({"sid": 1}, classifier_id=20, class_id=3)
        self.assertIn("FROM alerce_tap.object AS obj", query)
        self.assertIn("JOIN alerce_tap.probability AS prob", query)
        self.assertIn("obj.oid = prob.oid AND obj.sid = prob.sid", query)
        self.assertIn("obj.sid = 1", query)
        self.assertIn("prob.classifier_id = 20", query)
        self.assertIn("prob.class_id = 3", query)
        self.assertIn("prob.ranking = 1", query)
        self.assertIn("ORDER BY prob.probability DESC", query)
        self.assertNotIn("probability >=", query)

    def test_probability_threshold_appended_when_given(self):
        query = _build_tap_classifier_query({"sid": 1}, classifier_id=20, class_id=3, probability=0.9)
        self.assertIn("AND prob.probability >= 0.9", query)

    def test_shared_filters_use_obj_column_prefix(self):
        query = _build_tap_classifier_query(
            {"sid": 1, "ra": 305.58, "dec": -18.79, "radius": 3600.0, "ndet": [3]},
            classifier_id=20,
            class_id=3,
        )
        self.assertIn("CONTAINS(POINT('ICRS', obj.meanra, obj.meandec)", query)
        self.assertIn("AND obj.n_det >= 3", query)

    def test_page_size_and_order_override_probability_default(self):
        query = _build_tap_classifier_query(
            {"sid": 1, "page_size": 100, "order_by": "firstmjd", "order_mode": "ASC"}, classifier_id=20, class_id=3,
        )
        self.assertTrue(query.startswith("SELECT TOP 100 "))
        self.assertTrue(query.endswith(" ORDER BY obj.firstmjd ASC"))
        self.assertNotIn("ORDER BY prob.probability", query)


class TestQueryService(TestCase):
    def setUp(self):
        cache.clear()
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

    def test_lsst_non_numeric_oid_raises_query_service_error_without_querying(self):
        with self.assertRaises(QueryServiceError):
            self.ds.query_service({"oid": "1 OR 1=1", "sid": 1, "survey": "lsst"})
        self.mock_tap_service.search.assert_not_called()

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

    def test_results_annotated_with_explorer_url(self):
        self.mock_tap_service.search.return_value = [{"oid": 12345, "meanra": np.float64(10.0)}]
        lsst = self.ds.query_service({"sid": 1, "survey": "lsst", "classifiers": []})
        self.assertEqual(lsst[0]["alerce_url"], "https://lsst.alerce.online/object/12345?survey=lsst")

        self.mock_alerce.query_objects.return_value = {"items": [{"oid": "ZTF18aaaaaa"}]}
        ztf = self.ds.query_service({"survey": "ztf", "classifiers": []})
        self.assertEqual(ztf[0]["alerce_url"], "https://alerce.online/object/ZTF18aaaaaa")

    def test_results_table_links_oid_to_explorer(self):
        html = render_to_string(
            AlerceDataService.query_results_table,
            {"results": [
                {"id": 1, "oid": 12345, "alerce_url": "https://lsst.alerce.online/object/12345?survey=lsst"},
                {"id": 2, "oid": 67890},
            ]},
        )
        self.assertIn('<a href="https://lsst.alerce.online/object/12345?survey=lsst"', html)
        self.assertIn("67890", html)
        self.assertEqual(html.count("<a href="), 1)

    def test_lsst_diaobject_classifier_query_uses_tap_probability_join(self):
        """
        sid=1 (diaObject) classifier queries are wired to a TAP join against
        alerce_tap.probability: one classifier-taxonomy lookup (cached, resolves
        names to ids) plus one probability-join query per requested classifier.
        """
        classifiers = [{"classifier": "stamp_classifier_rubin_beta", "class": "SN", "probability": 0.9}]
        row = {"oid": 999, "meanra": np.float64(10.0), "n_det": np.int64(3),
               "probability": np.float64(0.95), "ranking": np.int64(1)}
        self.mock_tap_service.search.side_effect = [MOCK_LSST_TAP_CLASSIFIER_ROWS, [row]]

        result = self.ds.query_service({"sid": 1, "survey": "lsst", "classifiers": classifiers})

        self.assertEqual(self.mock_tap_service.search.call_count, 2)
        probability_query = self.mock_tap_service.search.call_args_list[1].args[0]
        self.assertIn("alerce_tap.probability", probability_query)
        self.assertIn("classifier_id = 20", probability_query)
        self.assertIn("class_id = 3", probability_query)
        self.assertIn("probability >= 0.9", probability_query)
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["ndet"], 3)

    def test_lsst_classifier_query_ranking_default_when_no_probability_threshold(self):
        classifiers = [{"classifier": "stamp_classifier_rubin_beta", "class": "SN", "probability": None}]
        self.mock_tap_service.search.side_effect = [MOCK_LSST_TAP_CLASSIFIER_ROWS, []]

        self.ds.query_service({"sid": 1, "survey": "lsst", "classifiers": classifiers})

        probability_query = self.mock_tap_service.search.call_args_list[1].args[0]
        self.assertNotIn("probability >=", probability_query)
        self.assertIn("ranking = 1", probability_query)

    def test_lsst_ssobject_classifier_query_raises_query_service_error(self):
        """
        Known ssObjects (sid=2) are pre-assigned probability 1 "asteroid" rather
        than classified, so classifier queries against sid=2 are rejected.
        """
        classifiers = [{"classifier": "stamp_classifier_rubin_beta", "class": "SN", "probability": 0.5}]
        with self.assertRaises(QueryServiceError):
            self.ds.query_service({"sid": 2, "survey": "lsst", "classifiers": classifiers})
        self.mock_tap_service.search.assert_not_called()

    def test_lsst_classifier_query_unknown_classifier_raises_query_service_error(self):
        classifiers = [{"classifier": "nonexistent_classifier", "class": "SN", "probability": 0.5}]
        self.mock_tap_service.search.return_value = MOCK_LSST_TAP_CLASSIFIER_ROWS
        with self.assertRaises(QueryServiceError):
            self.ds.query_service({"sid": 1, "survey": "lsst", "classifiers": classifiers})

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

    def test_lsst_detection_fixture_creates_reduced_datum(self):
        """
        LSST detections carry difference flux in nJy (`psfFlux`) and an integer
        `band`, not the ZTF REST shape's `magpsf`/`sigmapsf`/`fid`.
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
        datum = reduced_datums[0]
        self.assertAlmostEqual(datum.brightness, 31.4 - 2.5 * math.log10(123.4))
        self.assertIsNone(datum.brightness_error)
        self.assertEqual(datum.bandpass, "z")
        self.assertEqual(datum.unit, "mag")
        self.assertEqual(datum.telescope, "Rubin")
        self.assertEqual(datum.instrument, "LSSTCam")

    def test_lsst_detection_flux_error_and_band_name(self):
        target = Target.objects.create(name="LSST12345", type="SIDEREAL", ra=10.0, dec=-5.0)
        data = {
            "detections": [
                {"mjd": 61000.5, "psfFlux": 3631e9 * 1e-8, "psfFluxErr": 3631e9 * 1e-9,
                 "band": 6, "band_name": "u"},
            ],
        }
        datum = self.ds.create_reduced_datums_from_query(target, data=data)[0]
        # 1e-8 of the 3631 Jy AB reference -> 20 mag; 10% flux error -> ~0.1086 mag
        self.assertAlmostEqual(datum.brightness, 20.0, places=2)
        self.assertAlmostEqual(datum.brightness_error, 2.5 / math.log(10) * 0.1)
        self.assertEqual(datum.bandpass, "u")

    def test_lsst_detection_mjd_is_tai(self):
        target = Target.objects.create(name="LSST12345", type="SIDEREAL", ra=10.0, dec=-5.0)
        data = {"detections": [{"mjd": 61000.0, "psfFlux": 100.0, "band": 1}]}
        datum = self.ds.create_reduced_datums_from_query(target, data=data)[0]
        # TAI - UTC = 37 s since 2017
        expected = Time(61000.0, format="mjd", scale="tai").utc.to_datetime(TimezoneInfo())
        self.assertEqual(datum.timestamp, expected)
        self.assertEqual(datum.timestamp.second, 23)

    def test_lsst_non_positive_flux_detections_skipped(self):
        target = Target.objects.create(name="LSST12345", type="SIDEREAL", ra=10.0, dec=-5.0)
        data = {
            "detections": [
                {"mjd": 61000.0, "psfFlux": -50.0, "band": 1},
                {"mjd": 61001.0, "psfFlux": 0.0, "band": 1},
                {"mjd": 61002.0, "psfFlux": 100.0, "band": 1},
            ],
        }
        reduced_datums = self.ds.create_reduced_datums_from_query(target, data=data)
        self.assertEqual(len(reduced_datums), 1)
        self.assertEqual(reduced_datums[0].bandpass, "g")


# alerce_tap.lsst_mpc_orbits rows as returned by TAP (subset of columns). 2020 TE16 has
# 0.0 placeholders for a/mean_anomaly/mean_motion; 2000 SK234 has them populated.
MPC_ORBIT_2020_TE16 = {
    "ssobjectid": np.int64(21165806405629509), "designation": "2020 TE16",
    "a": np.float64(0.0), "q": np.float64(1.92531105668165), "e": np.float64(0.242376936145473),
    "i": np.float64(6.3219861793433), "node": np.float64(234.8308671640585),
    "argperi": np.float64(130.788251505259), "peri_time": np.float64(60558.1804330095),
    "mean_anomaly": np.float64(0.0), "mean_motion": np.float64(0.0), "epoch_mjd": np.float64(60600.0),
    "h": np.float64(19.474), "g": np.float64(0.15),
}
MPC_ORBIT_2000_SK234 = {
    "ssobjectid": np.int64(21163607367496779), "designation": "2000 SK234",
    "a": np.float64(2.7672962522372817), "q": np.float64(2.09903169657479), "e": np.float64(0.241486452750485),
    "i": np.float64(8.314624536688), "node": np.float64(67.0818177412172),
    "argperi": np.float64(277.5160290084402), "peri_time": np.float64(60182.875107613),
    "mean_anomaly": np.float64(174.9480202569077), "mean_motion": np.float64(0.21410193458476848),
    "epoch_mjd": np.float64(61000.0), "h": np.float64(16.297), "g": np.float64(0.15),
}


class TestSSObjectTargetCreation(TestCase):
    def setUp(self):
        self.ds = AlerceDataService()
        tap_patcher = patch("tom_dataservices.data_services.alerce.tap_service")
        self.mock_tap_service = tap_patcher.start()
        self.addCleanup(tap_patcher.stop)

    def _create(self, oid, orbit_rows):
        self.mock_tap_service.search.return_value = orbit_rows
        return self.ds.create_target_from_query(
            {"oid": oid, "sid": 2, "meanra": 151.18, "meandec": 1.91, "survey": "lsst"}
        )

    def test_ssobject_becomes_non_sidereal_minor_planet(self):
        target = self._create(21165806405629509, [MPC_ORBIT_2020_TE16])
        adql = self.mock_tap_service.search.call_args.args[0]
        self.assertIn("alerce_tap.lsst_mpc_orbits", adql)
        self.assertIn("ssObjectId = 21165806405629509", adql)
        self.assertEqual(target.name, 21165806405629509)
        self.assertEqual(target.type, Target.NON_SIDEREAL)
        self.assertEqual(target.scheme, "MPC_MINOR_PLANET")
        self.assertIsNone(target.ra)
        self.assertEqual(target.epoch_of_elements, 60600.0)
        self.assertEqual(target.inclination, 6.3219861793433)
        self.assertEqual(target.lng_asc_node, 234.8308671640585)
        self.assertEqual(target.arg_of_perihelion, 130.788251505259)
        self.assertEqual(target.eccentricity, 0.242376936145473)
        self.assertEqual(target.perihdist, 1.92531105668165)
        self.assertEqual(target.epoch_of_perihelion, 60558.1804330095)
        self.assertEqual(target.abs_mag, 19.474)
        self.assertEqual(target.slope, 0.15)
        self.assertIsInstance(target.eccentricity, float)
        # Derived rather than taken from the 0.0 placeholders
        self.assertAlmostEqual(target.semimajor_axis, 1.92531105668165 / (1 - 0.242376936145473))
        self.assertGreater(target.mean_anomaly, 0.0)

    def test_derived_elements_match_alerce_values_when_populated(self):
        target = self._create(21163607367496779, [MPC_ORBIT_2000_SK234])
        self.assertAlmostEqual(target.semimajor_axis, MPC_ORBIT_2000_SK234["a"], places=6)
        self.assertAlmostEqual(target.mean_daily_motion, MPC_ORBIT_2000_SK234["mean_motion"], places=6)
        self.assertAlmostEqual(target.mean_anomaly, MPC_ORBIT_2000_SK234["mean_anomaly"], places=3)

    def test_unbound_orbit_uses_comet_scheme(self):
        orbit = dict(MPC_ORBIT_2020_TE16, e=np.float64(1.05))
        target = self._create(21165806405629509, [orbit])
        self.assertEqual(target.scheme, "MPC_COMET")
        self.assertEqual(target.perihdist, 1.92531105668165)
        self.assertEqual(target.epoch_of_perihelion, 60558.1804330095)
        self.assertIsNone(target.semimajor_axis)
        self.assertIsNone(target.mean_anomaly)

    def test_ssobject_without_orbit_falls_back_to_sidereal(self):
        target = self._create(21165806405629509, [])
        self.assertEqual(target.type, "SIDEREAL")
        self.assertEqual(target.ra, 151.18)
        self.assertEqual(target.dec, 1.91)

    def test_diaobject_does_not_query_orbits(self):
        target = self.ds.create_target_from_query({"oid": 313853496686280764, "sid": 1, "meanra": 9.35,
                                                   "meandec": -42.46})
        self.assertEqual(target.type, "SIDEREAL")
        self.mock_tap_service.search.assert_not_called()

    def test_ssobject_target_saves(self):
        target = self._create(21165806405629509, [MPC_ORBIT_2020_TE16])
        target.save()
        self.assertEqual(Target.objects.get(pk=target.pk).scheme, "MPC_MINOR_PLANET")
