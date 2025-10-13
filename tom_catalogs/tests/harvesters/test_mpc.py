import json
from importlib_resources import files

from django.test import tag, TestCase
from unittest.mock import MagicMock, patch

from tom_catalogs.harvesters.mpc import MPCHarvester, MPCExplorerHarvester


class TestMPCHarvester(TestCase):
    def setUp(self):
        self.broker = MPCHarvester()
        self.test_response = [{'foo': 42}]
        self.test_obj1627_response = [{'absolute_magnitude': '12.79',
                                       'argument_of_perihelion': '167.84169',
                                       'ascending_node': '133.0747611',
                                       'designation': None,
                                       'eccentricity': '0.3972474',
                                       'epoch_jd': '2460800.5',
                                       'inclination': '8.45614',
                                       'mean_anomaly': '233.93148',
                                       'mean_daily_motion': '0.3875921',
                                       'name': 'Ivar',
                                       'neo': True,
                                       'number': 1627,
                                       'phase_slope': '0.6',
                                       'semimajor_axis': '1.86303'}]

    @patch('astroquery.mpc.MPC.query_object')
    def test_query_name(self, mock_query):
        mock_query.return_value = self.test_response

        self.broker.query('didymos')
        self.assertEqual(self.broker._object_type, 'asteroid')
        self.assertEqual(self.broker._object_term, 'didymos')
        self.assertEqual(self.broker._query_type, 'name')
        self.assertEqual(self.broker.catalog_data, self.test_response)

    @patch('astroquery.mpc.MPC.query_object')
    def test_query_asteroid_number(self, mock_query):
        mock_query.return_value = self.test_response

        self.broker.query('1627')
        self.assertEqual(self.broker._object_type, 'asteroid')
        self.assertEqual(self.broker._query_type, 'number')
        self.assertEqual(self.broker._object_term, '1627')
        self.assertEqual(self.broker.catalog_data, self.test_response)

    @patch('astroquery.mpc.MPC.query_object')
    def test_query_asteroid_number_ws(self, mock_query):
        mock_query.return_value = self.test_response

        self.broker.query('  1627    ')
        self.assertEqual(self.broker._object_type, 'asteroid')
        self.assertEqual(self.broker._query_type, 'number')
        self.assertEqual(self.broker._object_term, '1627')
        self.assertEqual(self.broker.catalog_data, self.test_response)

    @patch('astroquery.mpc.MPC.query_object')
    def test_query_comet_number(self, mock_query):
        mock_query.return_value = self.test_response

        self.broker.query('67P')
        self.assertEqual(self.broker._object_type, 'comet')
        self.assertEqual(self.broker._query_type, 'number')
        self.assertEqual(self.broker._object_term, '67P')
        self.assertEqual(self.broker.catalog_data, self.test_response)

    @patch('astroquery.mpc.MPC.query_object')
    def test_query_comet_number_ws(self, mock_query):
        mock_query.return_value = self.test_response

        self.broker.query('  67P    ')
        self.assertEqual(self.broker._object_type, 'comet')
        self.assertEqual(self.broker._query_type, 'number')
        self.assertEqual(self.broker._object_term, '67P')
        self.assertEqual(self.broker.catalog_data, self.test_response)

    @patch('astroquery.mpc.MPC.query_object')
    def test_query_provisional_cometlike(self, mock_query):
        # This tests if we have a provisional id such as '1999PA123' or '2025PM' which shouldn't
        # match with periodic comets despite being "number" followed by "P"
        mock_query.return_value = self.test_response

        self.broker.query('2025PM')
        self.assertNotEqual(self.broker._object_type, 'comet')
        self.assertNotEqual(self.broker._query_type, 'number')
        self.assertEqual(self.broker._object_term, '2025PM')
        self.assertEqual(self.broker.catalog_data, self.test_response)

    @patch('astroquery.mpc.MPC.query_object')
    def test_query_provisional_cometlike_ws(self, mock_query):
        # This tests if we have a provisional id such as '1999 PA123' or '2025 PM' which shouldn't
        # match with periodic comets despite being "number" followed by " P"
        mock_query.return_value = self.test_response

        self.broker.query('2025 PM')
        self.assertNotEqual(self.broker._object_type, 'comet')
        self.assertNotEqual(self.broker._query_type, 'number')
        self.assertEqual(self.broker._object_term, '2025 PM')
        self.assertEqual(self.broker.catalog_data, self.test_response)

    @patch('astroquery.mpc.MPC.query_object')
    def test_designation(self, mock_query):
        mock_query.return_value = self.test_response

        self.broker.query('2025 MB18')
        self.assertEqual(self.broker._object_type, 'asteroid')
        self.assertEqual(self.broker._query_type, 'desig')
        self.assertEqual(self.broker._object_term, '2025 MB18')
        self.assertEqual(self.broker.catalog_data, self.test_response)

    @patch('astroquery.mpc.MPC.query_object')
    def test_designation_cometish(self, mock_query):
        mock_query.return_value = self.test_response

        self.broker.query('2022PA')
        self.assertEqual(self.broker._object_type, 'asteroid')
        self.assertEqual(self.broker._query_type, 'desig')
        self.assertEqual(self.broker._object_term, '2022PA')
        self.assertEqual(self.broker.catalog_data, self.test_response)

    @patch('astroquery.mpc.MPC.query_object')
    def test_designation_cometish_with_ws(self, mock_query):
        mock_query.return_value = self.test_response

        self.broker.query('2022 PA')
        self.assertEqual(self.broker._object_type, 'asteroid')
        self.assertEqual(self.broker._query_type, 'desig')
        self.assertEqual(self.broker._object_term, '2022 PA')
        self.assertEqual(self.broker.catalog_data, self.test_response)

    @patch('astroquery.mpc.MPC.query_object')
    def test_designation_ws(self, mock_query):
        mock_query.return_value = self.test_response

        self.broker.query('  2025 MB18   ')
        self.assertEqual(self.broker._object_type, 'asteroid')
        self.assertEqual(self.broker._query_type, 'desig')
        self.assertEqual(self.broker._object_term, '2025 MB18')
        self.assertEqual(self.broker.catalog_data, self.test_response)

    @patch('astroquery.mpc.MPC.query_object')
    def test_designation_nospace(self, mock_query):
        mock_query.return_value = self.test_response

        self.broker.query('2025MB18')
        self.assertEqual(self.broker._object_type, 'asteroid')
        self.assertEqual(self.broker._query_type, 'desig')
        self.assertEqual(self.broker._object_term, '2025MB18')
        self.assertEqual(self.broker.catalog_data, self.test_response)

    @patch('astroquery.mpc.MPC.query_object')
    def test_provisional_comets(self, mock_query):
        mock_query.return_value = self.test_response

        comets = ['C/2024 S4', 'P/2017 A1', 'D/1853 X1', 'C/2001 OG108', 'P/2002 EJ57']
        for comet in comets:
            self.broker.query(comet)
            self.assertEqual(self.broker._object_type, 'comet', msg=f'Failure on _object_type for {comet}')
            self.assertEqual(self.broker._query_type, 'desig', msg=f'Failure on _query_type for {comet}')
            self.assertEqual(self.broker._object_term, comet, msg=f'Failure on _object_term for {comet}')
            self.assertEqual(self.broker.catalog_data, self.test_response)

    @patch('astroquery.mpc.MPC.query_object')
    def test_to_target_HG_fields(self, mock_query):
        mock_query.return_value = self.test_obj1627_response

        self.broker.query('1627')
        target = self.broker.to_target()
        target.save(names=getattr(target, 'extra_names', []))
        self.assertEqual(target.name, '1627')
        self.assertEqual(target.names, ['1627', 'Ivar'])
        self.assertEqual(target.type, 'NON_SIDEREAL')
        self.assertEqual(target.scheme, 'MPC_MINOR_PLANET')
        self.assertEqual(target.ra, None)
        self.assertEqual(target.dec, None)
        self.assertAlmostEqual(target.abs_mag, 12.79, places=3)
        self.assertAlmostEqual(target.slope, 0.6, places=3)


@tag('canary')
class TestMPCHarvesterCanary(TestCase):
    def setUp(self):
        self.broker = MPCHarvester()

    def test_query_number_only(self):
        self.broker.query('700000')
        target = self.broker.to_target()
        target.save(names=getattr(target, 'extra_names', []))
        # Only test things that are not likely to change (much) with time
        self.assertEqual(target.name, '700000')
        self.assertEqual(target.names, ['700000'])
        self.assertEqual(target.type, 'NON_SIDEREAL')
        self.assertEqual(target.scheme, 'MPC_MINOR_PLANET')
        self.assertEqual(target.ra, None)
        self.assertEqual(target.dec, None)
        self.assertAlmostEqual(target.eccentricity, 0.092, places=3)
        self.assertAlmostEqual(target.inclination, 4.1688, places=4)
        self.assertAlmostEqual(target.mean_anomaly, 315.8420, places=4)
        self.assertAlmostEqual(target.semimajor_axis, 2.6555, places=4)
        self.assertAlmostEqual(target.abs_mag, 17.76, places=2)
        self.assertAlmostEqual(target.slope, 0.15, places=2)

    def test_query_designation_only(self):
        self.broker.query('2025 MB18')
        target = self.broker.to_target()
        target.save(names=getattr(target, 'extra_names', []))
        # Only test things that are not likely to change (much) with time
        self.assertEqual(target.name, '2025 MB18')
        self.assertEqual(target.names, ['2025 MB18'])
        self.assertEqual(target.type, 'NON_SIDEREAL')
        self.assertEqual(target.scheme, 'MPC_MINOR_PLANET')
        self.assertEqual(target.ra, None)
        self.assertEqual(target.dec, None)
        self.assertAlmostEqual(target.eccentricity, 0.1398, places=4)
        self.assertAlmostEqual(target.inclination, 19.3561, places=4)
        self.assertAlmostEqual(target.abs_mag, 24.33, places=2)
        self.assertAlmostEqual(target.slope, 0.15, places=2)

    def test_query_name(self):
        self.broker.query('1627')
        target = self.broker.to_target()
        target.save(names=getattr(target, 'extra_names', []))
        # Only test things that are not likely to change (much) with time
        self.assertEqual(target.name, '1627')
        self.assertEqual(target.names, ['1627', 'Ivar'])
        self.assertEqual(target.type, 'NON_SIDEREAL')
        self.assertEqual(target.scheme, 'MPC_MINOR_PLANET')
        self.assertEqual(target.ra, None)
        self.assertEqual(target.dec, None)
        self.assertAlmostEqual(target.eccentricity, 0.3973229, places=3)
        self.assertAlmostEqual(target.inclination, 8.45629, places=3)
        self.assertAlmostEqual(target.abs_mag, 12.79, places=2)
        self.assertAlmostEqual(target.slope, 0.15, places=2)

    def test_query_comet_name(self):
        self.broker.query('29P')
        target = self.broker.to_target()
        target.save(names=getattr(target, 'extra_names', []))
        # Only test things that are not likely to change (much) with time
        self.assertEqual(target.name, '29P')
        self.assertEqual(target.names, ['29P'])
        self.assertEqual(target.type, 'NON_SIDEREAL')
        self.assertEqual(target.scheme, 'MPC_COMET')
        self.assertEqual(target.ra, None)
        self.assertEqual(target.dec, None)
        self.assertAlmostEqual(target.eccentricity, 0.043051, places=3)
        self.assertAlmostEqual(target.lng_asc_node, 312.401838, places=3)

    def test_query_comet_designation(self):
        self.broker.query('C/2017 K2')
        target = self.broker.to_target()
        target.save(names=getattr(target, 'extra_names', []))
        # Only test things that are not likely to change (much) with time
        self.assertEqual(target.name, 'C/2017 K2')
        self.assertEqual(target.names, ['C/2017 K2'])
        self.assertEqual(target.type, 'NON_SIDEREAL')
        self.assertEqual(target.scheme, 'MPC_COMET')
        self.assertEqual(target.ra, None)
        self.assertEqual(target.dec, None)
        self.assertAlmostEqual(target.perihdist, 1.8001, places=3)
        self.assertAlmostEqual(target.arg_of_perihelion, 236.15758, places=3)


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
        self.assertAlmostEqual(target.abs_mag, 18.105, places=3)
        self.assertAlmostEqual(target.slope, 0.15, places=2)
        self.assertEqual(target.ra, None)
        self.assertEqual(target.dec, None)
        self.assertEqual(target.pm_ra, None)
        self.assertEqual(target.pm_dec, None)

    def test_to_target_no_name(self):
        # Modify designation data to one with a provisional id only
        self.broker.catalog_data[0]['mpc_orb']['designation_data']['iau_name'] = ""
        del (self.broker.catalog_data[0]['mpc_orb']['designation_data']['name'])
        self.broker.catalog_data[0]['mpc_orb']['designation_data']['orbfit_name'] = "2025AA"
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
        self.assertAlmostEqual(target.abs_mag, 10.39, places=2)
        self.assertAlmostEqual(target.slope, 0.15, places=2)
