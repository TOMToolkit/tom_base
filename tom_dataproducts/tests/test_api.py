from django.contrib.auth.models import User
from django.urls import reverse
from guardian.shortcuts import assign_perm
from rest_framework import status
from rest_framework.test import APITestCase

from tom_dataproducts.models import DataProduct, ReducedDatum
from tom_observations.tests.factories import ObservingRecordFactory
from tom_targets.tests.factories import SiderealTargetFactory


class TestDataProductViewset(APITestCase):
    def setUp(self):
        user = User.objects.create(username='testuser')
        self.client.force_login(user)
        self.st = SiderealTargetFactory.create()
        self.obsr = ObservingRecordFactory.create(target_id=self.st.id)
        self.dp_data = {
            'product_id': 'test_product_id',
            'target': self.st.id,
            'data_product_type': 'photometry'
        }

        assign_perm('tom_dataproducts.add_dataproduct', user)
        assign_perm('tom_targets.add_target', user, self.st)
        assign_perm('tom_targets.view_target', user, self.st)
        assign_perm('tom_targets.change_target', user, self.st)

    def test_data_product_upload_for_target(self):
        with open('tom_dataproducts/tests/test_data/test_lightcurve.csv', 'rb') as lightcurve_file:
            self.dp_data['file'] = lightcurve_file
            response = self.client.post(reverse('api:dataproducts-list'), self.dp_data, format='multipart')
            self.assertEqual(response.status_code, status.HTTP_201_CREATED)
            self.assertEqual(DataProduct.objects.count(), 1)
            self.assertEqual(ReducedDatum.objects.count(), 3)
            dp = DataProduct.objects.get(pk=response.data['id'])
            self.assertEqual(dp.target_id, self.st.id)

    def test_data_product_upload_for_observation(self):
        self.dp_data['observation_record'] = self.obsr.id

        with open('tom_dataproducts/tests/test_data/test_lightcurve.csv', 'rb') as lightcurve_file:
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

        with open('tom_dataproducts/tests/test_data/test_lightcurve.csv', 'rb') as lightcurve_file:
            self.dp_data['file'] = lightcurve_file
            response = self.client.post(reverse('api:dataproducts-list'), self.dp_data, format='multipart')

            self.assertContains(response, 'Not a valid data_product_type.', status_code=status.HTTP_400_BAD_REQUEST)

    def test_data_product_upload_failed_processing(self):
        self.dp_data['data_product_type'] = 'spectroscopy'

        with open('tom_dataproducts/tests/test_data/test_lightcurve.csv', 'rb') as lightcurve_file:
            self.dp_data['file'] = lightcurve_file
            response = self.client.post(reverse('api:dataproducts-list'), self.dp_data, format='multipart')

            self.assertContains(
                response.data,
                'There was an error in processing your DataProduct into individual ReducedDatum objects.',
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
