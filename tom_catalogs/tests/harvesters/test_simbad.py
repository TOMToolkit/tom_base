from unittest.mock import MagicMock

from astroquery.exceptions import TableParseError
from astropy.table import Table
from django.test import tag, TestCase

from tom_catalogs.harvesters.simbad import SimbadHarvester


class TestSimbadHarvester(TestCase):
    def setUp(self):
        self.broker = SimbadHarvester()
        table_data = {'RA_d': [10.68470800], 'DEC_d': [41.26875000],
                      'PMRA': ['--'], 'PMDEC': ['--'], 'ID': ['M 31, 2C 56, DA 21'],
                      'Distance_distance': [0.8200]}
        self.broker.catalog_data = Table(table_data)

    def test_query_failure(self):
        self.broker.simbad = MagicMock()
        self.broker.simbad.query_object.side_effect = TableParseError()
        self.broker.query('M31')
        self.assertIsNone(self.broker.catalog_data)

    def test_to_target(self):
        target = self.broker.to_target()
        self.assertEqual(target.ra, self.broker.catalog_data['RA_d'])
        self.assertEqual(target.dec, self.broker.catalog_data['DEC_d'])
        self.assertEqual(target.pm_ra, None)
        self.assertEqual(target.pm_dec, None)
        self.assertEqual(target.distance, self.broker.catalog_data['Distance_distance'])
        self.assertEqual(target.name, 'M31')


@tag('canary')
class TestSimbadHarvesterCanary(TestCase):
    def setUp(self):
        self.broker = SimbadHarvester()

    def test_query(self):
        self.broker.query('HD 289002')
        target = self.broker.to_target()
        self.assertEqual(target.name, 'HD289002')
        self.assertAlmostEqual(target.ra, 101.306, places=3)
        self.assertAlmostEqual(target.dec, 2.137, places=3)
