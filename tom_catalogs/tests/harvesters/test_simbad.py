from unittest.mock import Mock

from astropy.table import Table
from django.test import tag, TestCase

from tom_catalogs.harvesters.simbad import SimbadHarvester


class TestSimbadHarvester(TestCase):
    def setUp(self):
        self.broker = SimbadHarvester()
        table_data = {'main_id': ['M  31'],
                      'ra': [10.684708333333333],
                      'dec': [41.268750000000004],
                      'pmra': ['--'],
                      'pmdec': ['--'],
                      'mesdistance.dist': [761.0],
                      'mesdistance.unit': ['kpc ']}
        self.broker.catalog_data = Table(table_data)
        self.empty_table_data = {'main_id': [],
                                 'ra': [],
                                 'dec': [],
                                 'pmra': [],
                                 'pmdec': [],
                                 'plx_value': [],
                                 'mesdistance.dist': [],
                                 'mesdistance.unit': []}

    def test_query_failure(self):
        self.broker.simbad.query_object = Mock(return_value=Table(self.empty_table_data))
        self.broker.query('M31')
        # Check that the empty table was returned and is falsey so it would trigger the MissingDataException in the
        # AbstractHarvester
        self.assertFalse(self.broker.catalog_data)

    def test_to_target(self):
        target = self.broker.to_target()
        self.assertEqual(target.ra, self.broker.catalog_data['ra'])
        self.assertEqual(target.dec, self.broker.catalog_data['dec'])
        self.assertEqual(target.pm_ra, None)
        self.assertEqual(target.pm_dec, None)
        self.assertEqual(target.distance, self.broker.catalog_data['mesdistance.dist'] * 1000)
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
