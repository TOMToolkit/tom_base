import json
from importlib_resources import files

from django.test import tag, TestCase
from unittest.mock import MagicMock, patch

from tom_dataservices.data_services.mpc import MPCExplorerDataService


class TestMPCExplorerDataService(TestCase):
    def setUp(self):
        self.ds = MPCExplorerDataService()
        test_json_fp = files('tom_catalogs.tests.harvesters.data').joinpath('test_65803_mpc_orb.json')
        test_json = json.loads(test_json_fp.read_text())
        self.ds.query_results = [{'mpc_orb': test_json},]

    @patch('requests.get')
    def test_query_failure_no_object(self, mock_get):
        """test query of non-existant object"""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.content = [None,  200]
        mock_get.return_value = mock_response

        result = self.ds.query_service({'desig': '123456P'})
        self.assertEqual(result, {})
        self.assertEqual(self.ds.query_results, {})

    def test_to_target(self):
        target = self.ds.to_target(self.ds.query_results[0])
        target.save(names=getattr(target, 'extra_names', []))
        self.assertEqual(target.type, 'NON_SIDEREAL')
        self.assertEqual(target.scheme, 'MPC_MINOR_PLANET')
        self.assertEqual(target.name, '65803')
        self.assertEqual(target.names, ['65803', 'Didymos', '1996 GT'])
        orbit_data = self.ds.query_results[0]['mpc_orb']
        elements = orbit_data['COM']['coefficient_values']
        self.assertEqual(target.epoch_of_elements, orbit_data['epoch_data']['epoch'])
        self.assertEqual(target.perihdist, elements[0])
        self.assertEqual(target.eccentricity, elements[1])
        self.assertEqual(target.inclination, elements[2])
        self.assertEqual(target.lng_asc_node, elements[3])
        self.assertEqual(target.arg_of_perihelion, elements[4])
        self.assertEqual(target.epoch_of_perihelion, elements[5])
        self.assertAlmostEqual(target.semimajor_axis, 1.6425997626135918, places=10)
        self.assertAlmostEqual(target.mean_daily_motion, 0.4681730823025772, places=10)
        self.assertAlmostEqual(target.mean_anomaly, 339.9299636288955, places=6)
        self.assertAlmostEqual(target.abs_mag, 18.105, places=3)
        self.assertAlmostEqual(target.slope, 0.15, places=2)
        self.assertEqual(target.ra, None)
        self.assertEqual(target.dec, None)
        self.assertEqual(target.pm_ra, None)
        self.assertEqual(target.pm_dec, None)

    def test_to_target_no_name(self):
        # Modify designation data to one with a provisional id only
        self.ds.query_results[0]['mpc_orb']['designation_data']['iau_name'] = ""
        del (self.ds.query_results[0]['mpc_orb']['designation_data']['name'])
        self.ds.query_results[0]['mpc_orb']['designation_data']['orbfit_name'] = "2025AA"
        self.ds.query_results[0]['mpc_orb']['designation_data']['unpacked_primary_provisional_designation'] = \
            "2025 AA"
        self.ds.query_results[0]['mpc_orb']['designation_data']['unpacked_secondary_provisional_designations'] = []

        target = self.ds.to_target(self.ds.query_results[0])
        target.save(names=getattr(target, 'extra_names', []))
        self.assertEqual(target.type, 'NON_SIDEREAL')
        self.assertEqual(target.scheme, 'MPC_MINOR_PLANET')
        self.assertEqual(target.name, '2025 AA')
        self.assertEqual(target.names, ['2025 AA'])

    def test_to_target_multiple_alternative_desigs(self):
        # Modify designation data to one with a provisional id only
        self.ds.query_results[0]['mpc_orb']['designation_data']['iau_name'] = ""
        self.ds.query_results[0]['mpc_orb']['designation_data']['name'] = 'Fringilla'
        self.ds.query_results[0]['mpc_orb']['designation_data']['orbfit_name'] = "709"
        self.ds.query_results[0]['mpc_orb']['designation_data']['unpacked_primary_provisional_designation'] = \
            "A911 CC"
        self.ds.query_results[0]['mpc_orb']['designation_data']['unpacked_secondary_provisional_designations'] = \
            [
                "A906 DA",
                "1948 PK1",
                "1956 CA"
            ]
        target = self.ds.to_target(self.ds.query_results[0])
        target.save(names=getattr(target, 'extra_names', []))
        self.assertEqual(target.type, 'NON_SIDEREAL')
        self.assertEqual(target.scheme, 'MPC_MINOR_PLANET')
        self.assertEqual(target.name, '709')
        self.assertEqual(target.names, ['709', 'Fringilla', 'A911 CC', 'A906 DA', '1948 PK1', '1956 CA'])

    def test_comet_to_target(self):
        # Make fake parabolic comet
        self.ds.query_results[0]['mpc_orb']['COM']['coefficient_values'][1] = 1.0
        self.ds.query_results[0]['mpc_orb']['categorization']['object_type_int'] = 10

        target = self.ds.to_target(self.ds.query_results[0])
        target.save(names=getattr(target, 'extra_names', []))
        self.assertEqual(target.type, 'NON_SIDEREAL')
        self.assertEqual(target.scheme, 'MPC_COMET')
        self.assertEqual(target.name, '65803')
        orbit_data = self.ds.query_results[0]['mpc_orb']
        elements = orbit_data['COM']['coefficient_values']
        self.assertEqual(target.epoch_of_elements, orbit_data['epoch_data']['epoch'])
        self.assertEqual(target.perihdist, elements[0])
        self.assertEqual(target.eccentricity, elements[1])
        self.assertEqual(target.inclination, elements[2])
        self.assertEqual(target.lng_asc_node, elements[3])
        self.assertEqual(target.arg_of_perihelion, elements[4])
        self.assertEqual(target.epoch_of_perihelion, elements[5])
        self.assertEqual(target.semimajor_axis, None)
        self.assertEqual(target.mean_daily_motion, None)
        self.assertEqual(target.mean_anomaly, None)
        self.assertEqual(target.ra, None)
        self.assertEqual(target.dec, None)
        self.assertEqual(target.pm_ra, None)
        self.assertEqual(target.pm_dec, None)

    def test_comet_to_target2(self):
        # Make fake near parabolic comet of right type
        self.ds.query_results[0]['mpc_orb']['COM']['coefficient_values'][1] = 0.999
        self.ds.query_results[0]['mpc_orb']['categorization']['object_type_int'] = 11

        target = self.ds.to_target(self.ds.query_results[0])
        target.save(names=getattr(target, 'extra_names', []))
        self.assertEqual(target.type, 'NON_SIDEREAL')
        self.assertEqual(target.scheme, 'MPC_COMET')
        self.assertEqual(target.name, '65803')
        orbit_data = self.ds.query_results[0]['mpc_orb']
        elements = orbit_data['COM']['coefficient_values']
        self.assertEqual(target.epoch_of_elements, orbit_data['epoch_data']['epoch'])
        self.assertEqual(target.perihdist, elements[0])
        self.assertEqual(target.eccentricity, elements[1])
        self.assertEqual(target.inclination, elements[2])
        self.assertEqual(target.lng_asc_node, elements[3])
        self.assertEqual(target.arg_of_perihelion, elements[4])
        self.assertEqual(target.epoch_of_perihelion, elements[5])
        self.assertEqual(target.semimajor_axis, None)
        self.assertEqual(target.mean_daily_motion, None)
        self.assertEqual(target.mean_anomaly, None)
        self.assertEqual(target.ra, None)
        self.assertEqual(target.dec, None)
        self.assertEqual(target.pm_ra, None)
        self.assertEqual(target.pm_dec, None)


@tag('canary')
class TestMPCExplorerDataServiceCanary(TestCase):
    def setUp(self):
        self.ds = MPCExplorerDataService()

    def test_query_neo(self):
        query_parameters = {'desig': '433'}
        self.ds.query_service(query_parameters)
        self.ds.query_targets(query_parameters)
        target = self.ds.to_target(self.ds.query_results[0])
        target.save(names=getattr(target, 'extra_names', []))
        # Only test things that are not likely to change (much) with time
        self.assertEqual(target.name, '433')
        self.assertEqual(target.names, ['433', 'Eros', 'A898 PA', '1956 PC'])
        self.assertEqual(target.type, 'NON_SIDEREAL')
        self.assertEqual(target.scheme, 'MPC_MINOR_PLANET')
        self.assertEqual(target.ra, None)
        self.assertEqual(target.dec, None)
        self.assertEqual(type(target.eccentricity), float)
        self.assertEqual(type(target.inclination), float)
        self.assertEqual(type(target.abs_mag), float)
        self.assertEqual(type(target.slope), float)
        self.assertAlmostEqual(target.slope, 0.15, places=2)

    def test_query_comet(self):
        query_parameters = {'desig': 'C/1995 O1'}
        self.ds.query_service(query_parameters)
        self.ds.query_targets(query_parameters)
        target = self.ds.to_target(self.ds.query_results[0])
        target.save(names=getattr(target, 'extra_names', []))
        # Only test things that are not likely to change (much) with time
        self.assertEqual(target.name, 'C/1995 O1')
        self.assertEqual(target.names, ['C/1995 O1', 'Hale-Bopp'])
        self.assertEqual(target.type, 'NON_SIDEREAL')
        self.assertEqual(target.scheme, 'MPC_COMET')
        self.assertEqual(target.ra, None)
        self.assertEqual(target.dec, None)
        self.assertEqual(type(target.perihdist), float)
        self.assertNotEqual(target.perihdist, None)
        self.assertEqual(type(target.eccentricity), float)
        self.assertEqual(type(target.inclination), float)
        self.assertEqual(type(target.abs_mag), float)
        self.assertEqual(type(target.slope), float)
        self.assertAlmostEqual(target.slope, 0.1, places=2)
