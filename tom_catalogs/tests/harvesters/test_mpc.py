import json
from importlib_resources import files

from django.test import tag, TestCase
from unittest.mock import MagicMock, patch

from tom_catalogs.harvesters.mpc import MPCExplorerHarvester


class TestMPCExplorerHarvester(TestCase):
    def setUp(self):
        self.broker = MPCExplorerHarvester()
        test_json_fp = files('tom_catalogs.tests.harvesters.data').joinpath('test_65803_mpc_orb.json')
        test_json = json.loads(test_json_fp.read_text())
        self.broker.catalog_data = [{'mpc_orb': test_json}, ]

    @patch('requests.get')
    def test_query_failure_no_object(self, mock_get):
        """test query of non-existant object"""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.content = [None,  200]
        mock_get.return_value = mock_response

        result = self.broker.query('123456P')
        self.assertEqual(result, None)
        self.assertIsNone(self.broker.catalog_data)

    def test_to_target(self):
        target = self.broker.to_target()
        target.save(names=getattr(target, 'extra_names', []))
        self.assertEqual(target.type, 'NON_SIDEREAL')
        self.assertEqual(target.scheme, 'MPC_MINOR_PLANET')
        self.assertEqual(target.name, '65803')
        self.assertEqual(target.names, ['65803', 'Didymos', '1996 GT'])
        orbit_data = self.broker.catalog_data[0]['mpc_orb']
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
        self.assertEqual(target.ra, None)
        self.assertEqual(target.dec, None)
        self.assertEqual(target.pm_ra, None)
        self.assertEqual(target.pm_dec, None)

    def test_to_target_no_name(self):
        # Modify designation data to one with a provisional id only
        self.broker.catalog_data[0]['mpc_orb']['designation_data']['iau_designation'] = "2025 AA"
        self.broker.catalog_data[0]['mpc_orb']['designation_data']['iau_name'] = ""
        del (self.broker.catalog_data[0]['mpc_orb']['designation_data']['name'])
        self.broker.catalog_data[0]['mpc_orb']['designation_data']['orbfit_name'] = "2025 AA"
        self.broker.catalog_data[0]['mpc_orb']['designation_data']['unpacked_primary_provisional_designation'] = \
            "2025 AA"
        self.broker.catalog_data[0]['mpc_orb']['designation_data']['unpacked_secondary_provisional_designations'] = []

        target = self.broker.to_target()
        target.save(names=getattr(target, 'extra_names', []))
        self.assertEqual(target.type, 'NON_SIDEREAL')
        self.assertEqual(target.scheme, 'MPC_MINOR_PLANET')
        self.assertEqual(target.name, '2025 AA')
        self.assertEqual(target.names, ['2025 AA'])

    def test_to_target_multiple_alternative_desigs(self):
        # Modify designation data to one with a provisional id only
        self.broker.catalog_data[0]['mpc_orb']['designation_data']['iau_designation'] = "(709)"
        self.broker.catalog_data[0]['mpc_orb']['designation_data']['iau_name'] = ""
        self.broker.catalog_data[0]['mpc_orb']['designation_data']['name'] = 'Fringilla'
        self.broker.catalog_data[0]['mpc_orb']['designation_data']['orbfit_name'] = "709"
        self.broker.catalog_data[0]['mpc_orb']['designation_data']['unpacked_primary_provisional_designation'] = \
            "A911 CC"
        self.broker.catalog_data[0]['mpc_orb']['designation_data']['unpacked_secondary_provisional_designations'] = \
            [
                "A906 DA",
                "1948 PK1",
                "1956 CA"
            ]
        target = self.broker.to_target()
        target.save(names=getattr(target, 'extra_names', []))
        self.assertEqual(target.type, 'NON_SIDEREAL')
        self.assertEqual(target.scheme, 'MPC_MINOR_PLANET')
        self.assertEqual(target.name, '709')
        self.assertEqual(target.names, ['709', 'Fringilla', 'A911 CC', 'A906 DA', '1948 PK1', '1956 CA'])

    def test_comet_to_target(self):
        # Make fake parabolic comet
        self.broker.catalog_data[0]['mpc_orb']['COM']['coefficient_values'][1] = 1.0
        self.broker.catalog_data[0]['mpc_orb']['categorization']['object_type_int'] = 10

        target = self.broker.to_target()
        target.save(names=getattr(target, 'extra_names', []))
        self.assertEqual(target.type, 'NON_SIDEREAL')
        self.assertEqual(target.scheme, 'MPC_COMET')
        self.assertEqual(target.name, '65803')
        orbit_data = self.broker.catalog_data[0]['mpc_orb']
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
        self.broker.catalog_data[0]['mpc_orb']['COM']['coefficient_values'][1] = 0.999
        self.broker.catalog_data[0]['mpc_orb']['categorization']['object_type_int'] = 11

        target = self.broker.to_target()
        target.save(names=getattr(target, 'extra_names', []))
        self.assertEqual(target.type, 'NON_SIDEREAL')
        self.assertEqual(target.scheme, 'MPC_COMET')
        self.assertEqual(target.name, '65803')
        orbit_data = self.broker.catalog_data[0]['mpc_orb']
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
class TestMPCExplorerHarvesterCanary(TestCase):
    def setUp(self):
        self.broker = MPCExplorerHarvester()

    def test_query_neo(self):
        self.broker.query('Eros')
        target = self.broker.to_target()
        target.save(names=getattr(target, 'extra_names', []))
        # Only test things that are not likely to change (much) with time
        self.assertEqual(target.name, '433')
        self.assertEqual(target.names, ['433', 'Eros', 'A898 PA', '1956 PC'])
        self.assertEqual(target.type, 'NON_SIDEREAL')
        self.assertEqual(target.scheme, 'MPC_MINOR_PLANET')
        self.assertEqual(target.ra, None)
        self.assertEqual(target.dec, None)
        self.assertAlmostEqual(target.eccentricity, 0.223, places=3)
        self.assertAlmostEqual(target.inclination, 10.828, places=3)
