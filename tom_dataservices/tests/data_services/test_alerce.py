from django.test import tag, TestCase

from tom_dataservices.data_services.alerce import AlerceDataService
from tom_targets.tests.factories import SiderealTargetFactory
from tom_dataproducts.models import PhotometryReducedDatum
from tom_dataservices.dataservices import QueryServiceError


class TestAlerceDataService(TestCase):
    def setUp(self):
        self.ds = AlerceDataService()
        self.target = SiderealTargetFactory.create()

    def test_create_reduced_datums_from_query(self):
        data = {'detections': [{'mjd': 58582,
                                'fid': 2,
                                'magpsf': 18.344053,
                                'sigmapsf': 0.05851808},
                                ]}
        data2 = {'detections': [{'mjd': 58583,
                                'fid': 2,
                                'magpsf': 19.344053,
                                'sigmapsf': 0.06851808},
                                ]}
        # Create new Photometry Datum
        self.ds.create_reduced_datums_from_query(self.target, data)
        self.assertEqual(PhotometryReducedDatum.objects.all().count(), 1)
        # Create 2nd photometry datum with different data
        self.ds.create_reduced_datums_from_query(self.target, data2)
        self.assertEqual(PhotometryReducedDatum.objects.all().count(), 2)

        # Change source in Phot datum
        datum = PhotometryReducedDatum.objects.get(brightness=18.344053)
        datum.source_name = "new_source"
        datum.save()

        # Try to create repeated Photometry Datum from different source
        new_datums = self.ds.create_reduced_datums_from_query(self.target, data)
        # Assert that source name was unchanged.
        self.assertEqual(new_datums[0].source_name, "new_source")

        # Change error in Phot datum
        datum = PhotometryReducedDatum.objects.get(brightness=18.344053)
        datum.brightness_error = 2
        datum.save()

        # Try to create repeated Photometry Datum with different brightness_error
        with self.assertRaises(QueryServiceError):
            new_datums = self.ds.create_reduced_datums_from_query(self.target, data)
