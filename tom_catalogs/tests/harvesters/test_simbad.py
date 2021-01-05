from django.test import tag, TestCase

from tom_catalogs.harvesters.simbad import SimbadHarvester


@tag('canary')
class TestSimbadHarvesterCanary(TestCase):
    def setUp(self):
        self.broker = SimbadHarvester()

    def test_query(self):
        self.broker.query('M31')
        target = self.broker.to_target()
        self.assertEqual(target.name, 'M31')
        self.assertAlmostEqual(target.ra, 10.684708, places=3)
        self.assertAlmostEqual(target.dec, 41.26875, places=3)
