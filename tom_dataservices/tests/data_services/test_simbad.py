from django.test import tag, TestCase

from tom_dataservices.data_services.simbad import SimbadDataService


@tag('canary')
class TestSimbadDataServiceCanary(TestCase):
    def setUp(self):
        self.ds = SimbadDataService()

    def test_query(self):
        query_parameters = {'search_term': 'M31'}
        target_results = self.ds.query_targets(query_parameters)
        target = self.ds.to_target(target_results[0])
        target.save(names=getattr(target, 'extra_names', []))
        self.assertEqual(target.name, 'M31')
        self.assertAlmostEqual(target.ra, 10.68, places=2)
        self.assertAlmostEqual(target.dec, 41.27, places=2)
