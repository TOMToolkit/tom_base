from unittest.mock import patch
import logging

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase  # , override_settings

from tom_dataproducts.models import DataProduct
from tom_dataproducts.processors.atlas_processor import AtlasProcessor


from tom_observations.tests.factories import SiderealTargetFactory

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)


class TestAtlasProcessor(TestCase):
    """Test the AtlasProcessor(DataProcessor) class.
    """

    def setUp(self):
        self.target = SiderealTargetFactory.create()
        self.data_product = DataProduct.objects.create(target=self.target)
        self.data_product_filefield_data = SimpleUploadedFile('nonsense.csv', b'somedata')

    @patch('tom_dataproducts.processors.atlas_processor.AtlasProcessor._process_photometry_from_plaintext')
    def test_process_photometry_with_plaintext_file(self, mocked_method):
        """Test that AtlasProcessor.process_data() calls AtlasProcessor._process_photometry_from_plaintext().
        """
        self.data_product.data.save('lightcurve.csv', self.data_product_filefield_data)

        # this is the call under test
        AtlasProcessor().process_data(self.data_product)
        mocked_method.assert_called_with(self.data_product)

    def test_mags_under_SN_cutoff_become_limits(self):
        """Test that magnitudes become limits when the flux S/N given by uJy/duJy
        is under the cutoff limit of 3.0. see https://fallingstar-data.com/forcedphot/resultdesc/

        The test data is an ATLAS forced photometry query on NGC1566 over the dates
        shown in the csv file.
        """
        # read the test data in as a data_product's data
        with open('tom_dataproducts/tests/test_data/test_atlas_fp.csv') as atlas_fp_file:
            self.data_product.data.save('test_data.csv', atlas_fp_file)

        # this is the call under test
        photometry = AtlasProcessor()._process_photometry_from_plaintext(self.data_product)

        expected_non_detection_count = 17  # known a priori from test data in test_atlas_fp.csv
        self.assertEqual(expected_non_detection_count,
                         len([datum for datum in photometry if 'limit' in datum.keys()]))
