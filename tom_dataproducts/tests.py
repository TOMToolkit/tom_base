from django.test import TestCase, override_settings
from django.contrib.auth.models import User
from django.core.files.uploadedfile import SimpleUploadedFile
from django.urls import reverse
from unittest.mock import patch
from datetime import date, time
from copy import copy

from tom_observations.tests.utils import FakeFacility
from tom_observations.tests.factories import TargetFactory, ObservingRecordFactory
from tom_dataproducts.models import DataProduct, PHOTOMETRY, SPECTROSCOPY
from tom_dataproducts.forms import DataProductUploadForm
from guardian.shortcuts import assign_perm


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


@override_settings(TOM_FACILITY_CLASSES=['tom_observations.tests.utils.FakeFacility'])
@patch('tom_dataproducts.models.DataProduct.get_image_data', return_value=b'image')
class TestUploadDataProducts(TestCase):
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

    def test_upload_spectrum_to_target(self):
        print(DataProductUploadForm())
        mock_return = [DataProduct(product_id='testdpid', data=SimpleUploadedFile('afile.fits', b'afile'))]
        response = self.client.post(
            reverse('dataproducts:upload'),
            {
                'facility': 'LCO',
                'files': SimpleUploadedFile('afile.fits', b'afile'),
                'target': self.target.id,
                'tag': SPECTROSCOPY[0],
                'observation_timestamp_0': date(2019, 6, 1),
                'observation_timestamp_1': time(12, 0, 0),
                'referrer': reverse('targets:detail', kwargs={'pk': self.target.id})
            },
            follow=True
        )
        self.assertContains(response, 'Successfully uploaded: afile.fits')


class TestDataUploadForms(TestCase):
    def setUp(self):
        self.target = TargetFactory.create()
        self.spectroscopy_form_data = {
            'target': self.target.id,
            'tag': SPECTROSCOPY[0],
            'facility': 'LCO',
            'observation_timestamp_0': date(2019, 6, 1),
            'observation_timestamp_1': time(12, 0, 0),
            'referrer': 'referrer'
        }
        self.photometry_form_data = {
            'target': self.target.id,
            'tag': PHOTOMETRY[0],
            'referrer': 'referrer'
        }
        self.file_data = {
            'files': SimpleUploadedFile('afile.fits', b'afile')
        }

    def test_form_spectroscopy_valid(self):
        form = DataProductUploadForm(self.spectroscopy_form_data, self.file_data)
        self.assertTrue(form.is_valid())

    def test_form_spectroscopy_no_timestamp(self):
        self.spectroscopy_form_data.pop('observation_timestamp_0')
        self.spectroscopy_form_data.pop('observation_timestamp_1')
        form = DataProductUploadForm(self.spectroscopy_form_data, self.file_data)
        self.assertFalse(form.is_valid())

    def test_form_spectroscopy_no_facility(self):
        self.spectroscopy_form_data.pop('facility')
        form = DataProductUploadForm(self.spectroscopy_form_data, self.file_data)
        self.assertFalse(form.is_valid())

    def test_form_photometry_valid(self):
        form = DataProductUploadForm(self.photometry_form_data, self.file_data)
        self.assertTrue(form.is_valid())

    def test_form_photometry_with_timestamp(self):
        self.photometry_form_data['facility'] = 'LCO'
        form = DataProductUploadForm(self.photometry_form_data, self.file_data)
        self.assertFalse(form.is_valid())

    def test_form_photometry_with_facility(self):
        self.photometry_form_data['observation_timestamp_0'] = date(2019, 6, 1)
        self.photometry_form_data['observation_timestamp_1'] = time(12, 0, 0)
        form = DataProductUploadForm(self.photometry_form_data, self.file_data)
        self.assertFalse(form.is_valid())
