from django.contrib.auth.models import Group, User
from django.core.files.uploadedfile import SimpleUploadedFile
from django.urls import reverse
from guardian.shortcuts import assign_perm
from rest_framework import status
from rest_framework.test import APITestCase

from bhtom_dataproducts.models import DataProduct, ReducedDatum
from bhtom_observations.tests.factories import ObservingRecordFactory
from bhtom_targets.tests.factories import SiderealTargetFactory


class TestDataProductViewset(APITestCase):
    def setUp(self):
        self.user = User.objects.create(username='testuser')
        self.client.force_login(self.user)
        self.st = SiderealTargetFactory.create()
        self.obsr = ObservingRecordFactory.create(target_id=self.st.id)
        self.dp_data = {
            'product_id': 'test_product_id',
            'target': self.st.id,
            'data_product_type': 'photometry'
        }

        assign_perm('bhtom_dataproducts.add_dataproduct', self.user)
        assign_perm('bhtom_targets.add_target', self.user, self.st)
        assign_perm('bhtom_targets.view_target', self.user, self.st)
        assign_perm('bhtom_targets.change_target', self.user, self.st)

    def test_data_product_upload_for_target(self):
        collaborator = User.objects.create(username='test collaborator')
        group = Group.objects.create(name='bourgeoisie')
        group.user_set.add(self.user)
        group.user_set.add(collaborator)

        with open('bhtom_base/bhtom_dataproducts/tests/test_data/test_lightcurve.csv', 'rb') as lightcurve_file:
            self.dp_data['file'] = lightcurve_file
            response = self.client.post(reverse('api:dataproducts-list'), self.dp_data, format='multipart')
            self.assertEqual(response.status_code, status.HTTP_201_CREATED)
            self.assertEqual(DataProduct.objects.count(), 1)
            self.assertEqual(ReducedDatum.objects.count(), 3)
            dp = DataProduct.objects.get(pk=response.data['id'])
            self.assertEqual(dp.target_id, self.st.id)

        # Test that group permissions are respected
        response = self.client.get(reverse('api:dataproducts-list'))
        self.assertContains(response, self.dp_data['product_id'], status_code=status.HTTP_200_OK)

    def test_data_product_upload_for_observation(self):
        self.dp_data['observation_record'] = self.obsr.id

        with open('bhtom_base/bhtom_dataproducts/tests/test_data/test_lightcurve.csv', 'rb') as lightcurve_file:
            self.dp_data['file'] = lightcurve_file
            response = self.client.post(reverse('api:dataproducts-list'), self.dp_data, format='multipart')

            self.assertEqual(response.status_code, status.HTTP_201_CREATED)
            self.assertEqual(DataProduct.objects.count(), 1)
            self.assertEqual(ReducedDatum.objects.count(), 3)
            dp = DataProduct.objects.get(pk=response.data['id'])
            self.assertEqual(dp.target_id, self.st.id)
            self.assertEqual(dp.observation_record_id, self.obsr.id)

    def test_data_product_upload_invalid_type(self):
        self.dp_data['data_product_type'] = 'invalid'

        with open('bhtom_base/bhtom_dataproducts/tests/test_data/test_lightcurve.csv', 'rb') as lightcurve_file:
            self.dp_data['file'] = lightcurve_file
            response = self.client.post(reverse('api:dataproducts-list'), self.dp_data, format='multipart')

            self.assertContains(response, 'Not a valid data_product_type.', status_code=status.HTTP_400_BAD_REQUEST)

    def test_data_product_upload_failed_processing(self):
        self.dp_data['data_product_type'] = 'spectroscopy'

        with open('bhtom_base/bhtom_dataproducts/tests/test_data/test_lightcurve.csv', 'rb') as lightcurve_file:
            self.dp_data['file'] = lightcurve_file
            response = self.client.post(reverse('api:dataproducts-list'), self.dp_data, format='multipart')

            self.assertContains(
                response,
                'There was an error in processing your DataProduct',
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    def test_data_product_delete(self):
        dp = DataProduct.objects.create(
            product_id='testproductid',
            target=self.st,
            data=SimpleUploadedFile('afile.fits', b'somedata')
        )
        assign_perm('bhtom_dataproducts.delete_dataproduct', self.user, dp)

        response = self.client.delete(reverse('api:dataproducts-detail', args=(dp.id,)))
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)

    def test_data_product_list(self):
        dp = DataProduct.objects.create(
            product_id='testproductid',
            target=self.st,
            data=SimpleUploadedFile('afile.fits', b'somedata')
        )

        response = self.client.get(reverse('api:dataproducts-list'))
        self.assertContains(response, dp.product_id, status_code=status.HTTP_200_OK)
