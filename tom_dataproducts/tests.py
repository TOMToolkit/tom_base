import tempfile

from django.test import TestCase, override_settings
from django.contrib.auth.models import User
from django.core.files.uploadedfile import SimpleUploadedFile
from django.urls import reverse
from unittest.mock import patch
from guardian.shortcuts import assign_perm

from tom_observations.tests.utils import FakeFacility
from tom_observations.tests.factories import TargetFactory, ObservingRecordFactory
from tom_dataproducts.models import DataProduct
from tom_dataproducts.utils import create_jpeg, create_image_dataproduct

def mock_fits2image(file1, file2, width, height):
    return True

def mock_find_img_size(filename):
    return (0,0)

@override_settings(TOM_FACILITY_CLASSES=['tom_observations.tests.utils.FakeFacility'])
@patch('tom_dataproducts.models.DataProduct.get_image_data', return_value=b'image')
class TestObservationDataViews(TestCase):
    def setUp(self):
        self.target = TargetFactory.create()
        self.observation_record = ObservingRecordFactory.create(
            target_id=self.target.id,
            facility=FakeFacility.name,
            parameters='{}'
        )
        self.data_product = DataProduct.objects.create(
            product_id='testproductid',
            target=self.target,
            observation_record=self.observation_record,
            data=SimpleUploadedFile('afile.fits', b'somedata')
        )
        user = User.objects.create_user(username='test', email='test@example.com')
        assign_perm('tom_targets.view_target', user, self.target)
        self.client.force_login(user)

    def test_dataproduct_list_on_target(self, dp_mock):
        response = self.client.get(reverse('tom_targets:detail', kwargs={'pk': self.target.id}))
        self.assertContains(response, 'afile.fits')

    def test_dataproduct_list(self, dp_mock):
        response = self.client.get(reverse('tom_dataproducts:list'))
        self.assertContains(response, 'afile.fits')

    def test_get_dataproducts(self, dp_mock):
        response = self.client.get(reverse('tom_observations:detail', kwargs={'pk': self.data_product.id}))
        self.assertContains(response, 'testdpid')

    def test_save_dataproduct(self, dp_mock):
        mock_return = [DataProduct(product_id='testdpid', data=SimpleUploadedFile('afile.fits', b'afile'))]
        with patch.object(FakeFacility, 'save_data_products', return_value=mock_return) as mock:
            response = self.client.post(
                reverse('dataproducts:save', kwargs={'pk': self.observation_record.id}),
                data={'facility': 'FakeFacility', 'products': ['testdpid']},
                follow=True
            )
            self.assertTrue(mock.called)
            self.assertContains(response, 'Successfully saved: afile.fits')

    @patch('tom_dataproducts.utils.fits_to_jpg', mock_fits2image)
    @patch('tom_dataproducts.utils.find_img_size', mock_find_img_size)
    def test_create_jpeg(self, dp_mock):
        products = DataProduct.objects.filter(tag='image_file')
        self.assertEqual(products.count(),0)
        resp = create_image_dataproduct(self.data_product)
        self.assertTrue(resp)
        products = DataProduct.objects.filter(tag='image_file')
        self.assertEqual(products.count(),1)
