from django.test import tag, TestCase
from unittest import mock

from tom_dataservices.data_services.jpl import ScoutDataService
# from tom_dataservices.tests.factories import scout_resultsFactory
from tom_targets.models import Target


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
