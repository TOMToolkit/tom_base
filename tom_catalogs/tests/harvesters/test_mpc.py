import json
from importlib_resources import files

from django.test import tag, TestCase
from unittest.mock import MagicMock

from tom_catalogs.harvesters.mpc import MPCExplorerHarvester


class TestMPCExplorerHarvester(TestCase):
    def setUp(self):
        self.broker = MPCExplorerHarvester()
        test_json_fp = files('tom_catalogs.tests.harvesters.data').joinpath('test_65803_mpc_orb.json')
        test_json = json.loads(test_json_fp.read_text())
        self.broker.catalog_data = [{'mpc_orb' : test_json}, ]

    def test_query_failure(self):
        # Much Mocking...
        pass

    def test_to_target(self):
        target = self.broker.to_target()
        self.assertEqual(target.type, 'NON_SIDEREAL')
        self.assertEqual(target.name, '(65803)')
        orbit_data = self.broker.catalog_data[0]['mpc_orb']
        elements = orbit_data['COM']['coefficient_values']
        self.assertEqual(target.epoch_of_elements, orbit_data['epoch_data']['epoch'])
        self.assertEqual(target.perihdist, elements[0])
        self.assertEqual(target.eccentricity, elements[1])
        self.assertEqual(target.inclination, elements[2])
        self.assertEqual(target.lng_asc_node, elements[3])
        self.assertEqual(target.arg_of_perihelion, elements[4])
        self.assertEqual(target.epoch_of_perihelion, elements[5])
        self.assertEqual(target.ra, None)
        self.assertEqual(target.dec, None)
        self.assertEqual(target.pm_ra, None)
        self.assertEqual(target.pm_dec, None)
