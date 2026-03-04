from django.test import tag, SimpleTestCase, TestCase
from unittest import mock

from tom_dataservices.data_services.jpl import ScoutDataService
# from tom_dataservices.tests.factories import scout_resultsFactory
from tom_targets.models import Target


def make_result(overrides=None):
    """Return a minimal valid Scout result dict, with optional field overrides."""
    base = {
        'objectName': 'ZTF10BL',
        'neoScore': 100,
        'phaScore': 0,
        'geocentricScore': 1,
        'rating': 2,
        'unc': '1400',
        'caDist': '0.98',
    }
    if overrides:
        base.update(overrides)
    return base


def make_result_with_orbits(overrides=None):
    """Return a Scout result that already contains orbit data (per-object query response)."""
    result = make_result(overrides)
    result['orbits'] = {
        'fields': ['idx', 'epoch', 'ec', 'qr', 'tp', 'om', 'w', 'inc', 'H',
                   'dca', 'tca', 'moid', 'vinf', 'geoEcc', 'impFlag'],
        'data': [[0, '2461079.712931752', '8.855752093403347E-01', '4.998861947435592E-01',
                  '2461038.529885748', '1.3898404962804094E+02', '2.6665272638172337E+02',
                  '1.4692644033445657E+01', '25.402927', '4.34144690247134E-03',
                  '2.4610794091831E+06', '1.971147172E-03', '2.790457665E+01',
                  '1.278753791E+03', 0]],
        'count': '1',
    }
    return result


class TestGetFilterThresholds(SimpleTestCase):
    """Tests for ScoutDataService._get_filter_thresholds()"""

    def setUp(self):
        self.ds = ScoutDataService()

    def _set_input_params(self, overrides=None):
        params = {
            'neo_score_min': None,
            'pha_score_min': None,
            'geo_score_max': None,
            'impact_rating_min': None,
            'ca_dist_min': None,
            'pos_unc_min': None,
            'pos_unc_max': None,
        }
        if overrides:
            params.update(overrides)
        self.ds.input_parameters = params

    def test_all_none_returns_permissive_defaults(self):
        """When all optional params are None, defaults should allow everything through."""
        self._set_input_params()
        thresholds = self.ds._get_filter_thresholds()

        self.assertEqual(thresholds['neo_score_min'], 0)
        self.assertEqual(thresholds['pha_score_min'], 0)
        self.assertEqual(thresholds['geo_score_max'], 101)
        self.assertEqual(thresholds['pos_unc_min'], 0)
        self.assertEqual(thresholds['pos_unc_max'], 360 * 60)
        self.assertIsNone(thresholds['impact_rating_min'])
        self.assertIsNone(thresholds['ca_dist_min'])

    def test_explicit_values_are_used(self):
        """Explicitly set values should be returned as-is."""
        self._set_input_params({
            'neo_score_min': 50,
            'pha_score_min': 10,
            'geo_score_max': 3,
            'pos_unc_min': 5,
            'pos_unc_max': 120,
            'impact_rating_min': 1,
            'ca_dist_min': 0.5,
        })
        thresholds = self.ds._get_filter_thresholds()

        self.assertEqual(thresholds['neo_score_min'], 50)
        self.assertEqual(thresholds['pha_score_min'], 10)
        self.assertEqual(thresholds['geo_score_max'], 3)
        self.assertEqual(thresholds['pos_unc_min'], 5)
        self.assertEqual(thresholds['pos_unc_max'], 120)
        self.assertEqual(thresholds['impact_rating_min'], 1)
        self.assertEqual(thresholds['ca_dist_min'], 0.5)

    def test_zero_values_are_preserved_not_replaced_by_default(self):
        """Explicit zero should be kept, not treated as falsy and replaced by a default."""
        self._set_input_params({'neo_score_min': 0, 'pha_score_min': 0, 'pos_unc_min': 0})
        thresholds = self.ds._get_filter_thresholds()

        self.assertEqual(thresholds['neo_score_min'], 0)
        self.assertEqual(thresholds['pha_score_min'], 0)
        self.assertEqual(thresholds['pos_unc_min'], 0)


class TestParseResultValues(SimpleTestCase):
    """Tests for ScoutDataService._parse_result_values()"""

    def setUp(self):
        self.ds = ScoutDataService()

    def test_valid_numeric_strings(self):
        result = make_result({'unc': '1400', 'caDist': '0.98'})
        pos_unc, ca_dist = self.ds._parse_result_values(result)

        self.assertEqual(pos_unc, 1400.0)
        self.assertAlmostEqual(ca_dist, 0.98)

    def test_non_numeric_unc_defaults_to_zero(self):
        """If 'unc' cannot be cast to float, pos_unc should default to 0.0."""
        result = make_result({'unc': 'N/A'})
        pos_unc, _ = self.ds._parse_result_values(result)

        self.assertEqual(pos_unc, 0.0)

    def test_none_ca_dist_returns_none(self):
        """A None 'caDist' (as returned by the API when unknown) should yield None."""
        result = make_result({'caDist': None})
        _, ca_dist = self.ds._parse_result_values(result)

        self.assertIsNone(ca_dist)

    def test_non_numeric_ca_dist_returns_none(self):
        """A non-numeric 'caDist' string that raises TypeError should yield None."""
        result = make_result({'caDist': 'unknown'})
        _, ca_dist = self.ds._parse_result_values(result)

        self.assertIsNone(ca_dist)


class TestPassesFilters(SimpleTestCase):
    """Tests for ScoutDataService._passes_filters()"""

    def setUp(self):
        self.ds = ScoutDataService()
        # Permissive thresholds that let everything through by default
        self.permissive = {
            'neo_score_min': 0,
            'pha_score_min': 0,
            'geo_score_max': 101,
            'impact_rating_min': None,
            'ca_dist_min': None,
            'pos_unc_min': 0,
            'pos_unc_max': 360 * 60,
        }

    def _thresholds(self, overrides=None):
        t = dict(self.permissive)
        if overrides:
            t.update(overrides)
        return t

    def test_passes_with_permissive_thresholds(self):
        result = make_result()
        self.assertTrue(self.ds._passes_filters(result, 1400.0, 0.98, self._thresholds()))

    def test_fails_neo_score_below_minimum(self):
        result = make_result({'neoScore': 30})
        self.assertFalse(self.ds._passes_filters(result, 0.0, None, self._thresholds({'neo_score_min': 50})))

    def test_fails_pha_score_below_minimum(self):
        result = make_result({'phaScore': 0})
        self.assertFalse(self.ds._passes_filters(result, 0.0, None, self._thresholds({'pha_score_min': 5})))

    def test_fails_geocentric_score_at_or_above_maximum(self):
        result = make_result({'geocentricScore': 5})
        self.assertFalse(self.ds._passes_filters(result, 0.0, None, self._thresholds({'geo_score_max': 5})))

    def test_passes_geocentric_score_strictly_below_maximum(self):
        result = make_result({'geocentricScore': 4})
        self.assertTrue(self.ds._passes_filters(result, 0.0, None, self._thresholds({'geo_score_max': 5})))

    def test_fails_pos_unc_below_minimum(self):
        result = make_result()
        self.assertFalse(self.ds._passes_filters(result, 50.0, None, self._thresholds({'pos_unc_min': 100})))

    def test_fails_pos_unc_above_maximum(self):
        result = make_result()
        self.assertFalse(self.ds._passes_filters(result, 500.0, None, self._thresholds({'pos_unc_max': 100})))

    def test_passes_when_impact_rating_min_is_none(self):
        """impact_rating_min=None means no impact filter — any rating (or None) should pass."""
        result = make_result({'rating': None})
        self.assertTrue(self.ds._passes_filters(result, 0.0, None, self._thresholds({'impact_rating_min': None})))

    def test_fails_when_rating_is_none_and_impact_rating_min_is_set(self):
        """If a minimum rating is required but the result has no rating, it should be filtered out."""
        result = make_result({'rating': None})
        self.assertFalse(self.ds._passes_filters(result, 0.0, None, self._thresholds({'impact_rating_min': 1})))

    def test_fails_when_rating_below_minimum(self):
        result = make_result({'rating': 1})
        self.assertFalse(self.ds._passes_filters(result, 0.0, None, self._thresholds({'impact_rating_min': 2})))

    def test_passes_when_ca_dist_min_is_none(self):
        """ca_dist_min=None means no close-approach filter."""
        result = make_result()
        self.assertTrue(self.ds._passes_filters(result, 0.0, None, self._thresholds({'ca_dist_min': None})))

    def test_fails_when_ca_dist_exceeds_minimum(self):
        """Result should be filtered out when its caDist is greater than the threshold."""
        result = make_result()
        self.assertFalse(self.ds._passes_filters(result, 0.0, 1.5, self._thresholds({'ca_dist_min': 1.0})))

    def test_fails_when_ca_dist_required_but_is_none(self):
        """If a ca_dist_min threshold is set but the result has no caDist, filter it out."""
        result = make_result()
        self.assertFalse(self.ds._passes_filters(result, 0.0, None, self._thresholds({'ca_dist_min': 1.0})))

    def test_passes_when_ca_dist_within_minimum(self):
        result = make_result()
        self.assertTrue(self.ds._passes_filters(result, 0.0, 0.5, self._thresholds({'ca_dist_min': 1.0})))


class TestFetchTargetData(SimpleTestCase):
    """Tests for ScoutDataService._fetch_target_data()"""

    def setUp(self):
        self.ds = ScoutDataService()
        self.query_parameters = {'tdes': ''}

    def test_returns_result_directly_when_orbits_present(self):
        """If the result already has orbit data, no additional query_service call should be made."""
        result = make_result_with_orbits()
        with mock.patch.object(self.ds, 'query_service') as mock_qs:
            target_data = self.ds._fetch_target_data(result, self.query_parameters)

        mock_qs.assert_not_called()
        self.assertEqual(target_data, result)

    def test_fetches_per_object_data_when_orbits_absent(self):
        """If orbits are not present, query_service should be called to fetch per-object data."""
        result = make_result()  # no 'orbits' key
        per_object_result = make_result_with_orbits()

        with mock.patch.object(self.ds, 'query_service', return_value=[per_object_result]) as mock_qs:
            with mock.patch.object(self.ds, 'get_urls', return_value='http://mock-url'):
                target_data = self.ds._fetch_target_data(result, self.query_parameters)

        mock_qs.assert_called_once()
        self.assertEqual(target_data, per_object_result)

    def test_sets_tdes_on_query_parameters_when_fetching(self):
        """query_parameters['tdes'] should be updated to the result's objectName before fetching."""
        result = make_result({'objectName': 'ZTF10BL'})
        per_object_result = make_result_with_orbits()

        with mock.patch.object(self.ds, 'query_service', return_value=[per_object_result]):
            with mock.patch.object(self.ds, 'get_urls', return_value='http://mock-url'):
                self.ds._fetch_target_data(result, self.query_parameters)

        self.assertEqual(self.query_parameters['tdes'], 'ZTF10BL')

    def test_returns_none_when_query_service_returns_none(self):
        """If the per-object query_service call returns None, _fetch_target_data should return None."""
        result = make_result()  # no 'orbits' key

        with mock.patch.object(self.ds, 'query_service', return_value=None):
            with mock.patch.object(self.ds, 'get_urls', return_value='http://mock-url'):
                target_data = self.ds._fetch_target_data(result, self.query_parameters)

        self.assertIsNone(target_data)


class TestQueryTargetsFiltering(TestCase):
    """Integration-level tests for query_targets filtering behaviour using mocked query_service."""

    def setUp(self):
        self.ds = ScoutDataService()
        self.base_input_parameters = {
            'ca_dist_min': None,
            'data_service': 'Scout',
            'geo_score_max': 5,
            'impact_rating_min': None,
            'neo_score_min': None,
            'pha_score_min': None,
            'pos_unc_max': None,
            'pos_unc_min': None,
            'query_name': '',
            'query_save': False,
            'tdes': 'ZTF10BL',
        }

    @mock.patch('tom_dataservices.data_services.jpl.ScoutDataService.query_service')
    def test_returns_empty_list_when_query_service_returns_none(self, mock_qs):
        mock_qs.return_value = None
        targets = self.ds.query_targets(self.base_input_parameters)
        self.assertEqual(targets, [])

    @mock.patch('tom_dataservices.data_services.jpl.ScoutDataService.query_service')
    def test_result_excluded_by_geocentric_score_filter(self, mock_qs):
        """A result with geocentricScore >= geo_score_max should be excluded."""
        result = make_result_with_orbits({'geocentricScore': 5})  # fails geo_score_max=5
        mock_qs.return_value = [result]

        targets = self.ds.query_targets(self.base_input_parameters)
        self.assertEqual(targets, [])

    @mock.patch('tom_dataservices.data_services.jpl.ScoutDataService.query_service')
    def test_result_included_when_all_filters_pass(self, mock_qs):
        """A result that satisfies all default filters should be included."""
        result = make_result_with_orbits({'geocentricScore': 1})
        mock_qs.return_value = [result]

        targets = self.ds.query_targets(self.base_input_parameters)
        self.assertEqual(len(targets), 1)
        self.assertEqual(targets[0]['objectName'], 'ZTF10BL')

    @mock.patch('tom_dataservices.data_services.jpl.ScoutDataService.query_service')
    def test_multiple_results_partial_filter(self, mock_qs):
        """Only results passing all filters should be returned from a multi-result response."""
        passing = make_result_with_orbits({'objectName': 'ZTF10BL', 'geocentricScore': 1})
        failing = make_result_with_orbits({'objectName': 'ZTF99XX', 'geocentricScore': 5})
        mock_qs.return_value = [passing, failing]

        targets = self.ds.query_targets(self.base_input_parameters)
        self.assertEqual(len(targets), 1)
        self.assertEqual(targets[0]['objectName'], 'ZTF10BL')


class TestScoutDataService(TestCase):
    """
    Test the functionality of the JPL ScoutDataService
    """
    def setUp(self):
        self.jpl_ds = ScoutDataService()
        self.input_parameters = {'ca_dist_min': None,
                                 'data_service': 'Scout',
                                 'geo_score_max': 5,
                                 'impact_rating_min': None,
                                 'neo_score_min': None,
                                 'pha_score_min': None,
                                 'pos_unc_max': None,
                                 'pos_unc_min': None,
                                 'query_name': '',
                                 'query_save': False,
                                 'tdes': ''}
        self.scout_results = [{'uncP1': '1500',
                               'tEphem': '2026-02-11 22:45',
                               'caDist': '0.98',
                               'phaScore': 0,
                               'vInf': '20.1',
                               'moid': '0.001',
                               'ra': '08:54',
                               'objectName': 'ZTF10BL',
                               'neo1kmScore': 0,
                               'geocentricScore': 1,
                               'rate': '1.9',
                               'Vmag': '20.8',
                               'dec': '+28',
                               'tisserandScore': 39,
                               'rating': 2,
                               'arc': '0.35',
                               'H': '26.3',
                               'elong': '156',
                               'unc': '1400',
                               'ieoScore': 0,
                               'orbits': {'data': [[0,
                                                    '2461079.712931752',
                                                    '8.855752093403347E-01',
                                                    '4.998861947435592E-01',
                                                    '2461038.529885748',
                                                    '1.3898404962804094E+02',
                                                    '2.6665272638172337E+02',
                                                    '1.4692644033445657E+01',
                                                    '25.402927',
                                                    '4.34144690247134E-03',
                                                    '2.4610794091831E+06',
                                                    '1.971147172E-03',
                                                    '2.790457665E+01',
                                                    '1.278753791E+03',
                                                    0]],
                                          'count': '1',
                                          'fields': ['idx',
                                                     'epoch',
                                                     'ec',
                                                     'qr',
                                                     'tp',
                                                     'om',
                                                     'w',
                                                     'inc',
                                                     'H',
                                                     'dca',
                                                     'tca',
                                                     'moid',
                                                     'vinf',
                                                     'geoEcc',
                                                     'impFlag']},
                               'nObs': 4,
                               'rmsN': '0.12',
                               'signature': {'source': 'NASA/JPL Scout API', 'version': '1.3'},
                               'lastRun': '2026-02-08 13:52',
                               'neoScore': 100},]

        target_params = {'name': 'ZTF10BL',
                         'type': 'NON-SIDEREAL',
                         'permissions': 'OPEN',
                         'scheme': 'MPC_MINOR_PLANET',
                         'epoch_of_elements': 61079.212931752,
                         'mean_anomaly': 4.4452481923884894,
                         'arg_of_perihelion': 266.65272638172337,
                         'eccentricity': 0.8855752093403347,
                         'lng_asc_node': 138.98404962804094,
                         'inclination': 14.692644033445657,
                         'mean_daily_motion': 0.10793879092762414,
                         'semimajor_axis': 4.368687867914702,
                         'epoch_of_perihelion': 61038.029885748,
                         'perihdist': 0.4998861947435592,
                         'abs_mag': 25.402927,
                         'slope': 0.15}
        self.test_target = Target.objects.create(**target_params)

    def test_build_query_parameters_no_target(self):
        """
        Test that the build_query_parameters method correctly builds the query parameters for the JPL ScoutDataService
        """
        expected_parameters = {}

        parameters = self.jpl_ds.build_query_parameters(self.input_parameters)

        self.assertEqual(parameters, expected_parameters)
        self.assertEqual(self.jpl_ds.input_parameters, self.input_parameters)

    def test_build_query_parameters_with_target(self):
        """
        Test that the build_query_parameters method correctly builds the query parameters for the JPL ScoutDataService
        """
        self.input_parameters['tdes'] = 'ZTF10BL'
        expected_parameters = {'tdes': 'ZTF10BL', 'orbits': 1, 'n-orbits': 1}
        parameters = self.jpl_ds.build_query_parameters(self.input_parameters)

        self.assertEqual(parameters, expected_parameters)
        self.assertEqual(self.jpl_ds.input_parameters, self.input_parameters)

    @mock.patch('tom_dataservices.data_services.jpl.ScoutDataService.query_service')
    def test_query_targets_single(self, mock_client):
        mock_client.side_effect = [self.scout_results, ]
        self.input_parameters['tdes'] = 'ZTF10BL'

        targets = self.jpl_ds.query_targets(self.input_parameters)
        expected_target_results = {'objectName': self.scout_results[0]['objectName'],
                                   'neoScore': self.scout_results[0]['neoScore'],
                                   'phaScore': self.scout_results[0]['phaScore'],
                                   'geocentricScore': self.scout_results[0]['geocentricScore'],
                                   'rating': self.scout_results[0]['rating'],
                                   'unc': self.scout_results[0]['unc'],
                                   'orbits': self.scout_results[0]['orbits'],
                                   }
        for target in targets:
            for key in expected_target_results.keys():
                if key == 'orbits':
                    self.assertEqual(type(target[key]), type(expected_target_results[key]))
                    self.assertEqual(type(target[key]['data']), type(expected_target_results[key]['data']))
                else:
                    self.assertEqual(target[key], expected_target_results[key])

    def test_create_target_from_query(self):
        expected_target = self.test_target

        target = self.jpl_ds.create_target_from_query(self.scout_results[0])

        self.assertEqual(target.name, expected_target.name)
        self.assertEqual(target.type, expected_target.type)
        self.assertEqual(target.ra, expected_target.ra)
        self.assertEqual(target.dec, expected_target.dec)
        self.assertEqual(target.scheme, expected_target.scheme)
        self.assertEqual(target.epoch_of_elements, expected_target.epoch_of_elements)
        self.assertAlmostEqual(target.mean_anomaly, expected_target.mean_anomaly, places=6)


@tag('canary')
class TestScoutDataServiceCanary(TestCase):
    """Tests that actually hit the JPL Scout API."""

    def setUp(self):
        self.jpl_ds = ScoutDataService()
        self.input_parameters = {'ca_dist_min': None,
                                 'data_service': 'Scout',
                                 'geo_score_max': 5,
                                 'impact_rating_min': None,
                                 'neo_score_min': None,
                                 'pha_score_min': None,
                                 'pos_unc_max': None,
                                 'pos_unc_min': None,
                                 'query_name': '',
                                 'query_save': False,
                                 'tdes': ''}
        self.expected_result_keys = ['lastRun', 'neo1kmScore', 'phaScore', 'geocentricScore', 'arc', 'rate',
                                     'neoScore', 'rating', 'elong', 'uncP1', 'vInf', 'objectName', 'dec', 'H',
                                     'caDist', 'moid', 'ra', 'unc', 'Vmag', 'nObs', 'rmsN', 'tEphem',
                                     'tisserandScore', 'ieoScore']

    def test_boilerplate(self):
        self.assertTrue(True)

    def test_query_service(self):
        """Test query_service."""
        results = self.jpl_ds.query_service(self.jpl_ds.build_query_parameters(self.input_parameters))

        self.assertIsNotNone(results)
        self.assertIsInstance(results, list)
        for key in results[0].keys():
            self.assertIn(key, self.expected_result_keys)

    def test_query_targets_single(self):
        """Test query_targets with a single result."""
        pass

    def test_create_target_from_query(self):
        """Test create_target_from_query."""
        pass
