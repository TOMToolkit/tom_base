from django.contrib.auth.models import Group, User
from django.core.files.uploadedfile import SimpleUploadedFile
from django.urls import reverse
from django.core.exceptions import ValidationError
from guardian.shortcuts import assign_perm
from rest_framework import status
from rest_framework.test import APITestCase

from tom_dataproducts.models import DataProduct, ReducedDatum
from tom_observations.tests.factories import ObservingRecordFactory
from tom_targets.tests.factories import SiderealTargetFactory


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

        assign_perm('tom_dataproducts.add_dataproduct', self.user)
        assign_perm('tom_targets.add_target', self.user, self.st)
        assign_perm('tom_targets.view_target', self.user, self.st)
        assign_perm('tom_targets.change_target', self.user, self.st)

    def test_data_product_upload_for_target(self):
        collaborator = User.objects.create(username='test collaborator')
        group = Group.objects.create(name='bourgeoisie')
        group.user_set.add(self.user)
        group.user_set.add(collaborator)

        with open('tom_dataproducts/tests/test_data/test_lightcurve.csv', 'rb') as lightcurve_file:
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
        assign_perm('tom_dataproducts.delete_dataproduct', self.user, dp)

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


class TestReducedDatumViewset(APITestCase):
    def setUp(self):
        self.user = User.objects.create(username='testuser')
        self.client.force_login(self.user)
        self.st = SiderealTargetFactory.create()
        self.obsr = ObservingRecordFactory.create(target_id=self.st.id)
        self.rd_data = {
            'data_product': '',
            'data_type': 'photometry',
            'source_name': 'TOM Toolkit',
            'source_location': 'TOM-TOM Direct Sharing',
            'value': {'magnitude': 15.582, 'filter': 'r', 'error': 0.005},
            'target': self.st.id,
            'timestamp': '2012-02-12T01:40:47Z'
        }

        assign_perm('tom_dataproducts.add_reduceddatum', self.user)
        assign_perm('tom_targets.add_target', self.user, self.st)
        assign_perm('tom_targets.view_target', self.user, self.st)
        assign_perm('tom_targets.change_target', self.user, self.st)

    def test_upload_reduced_datum(self):
        response = self.client.post(reverse('api:reduceddatums-list'), self.rd_data, format='json')
        self.assertContains(response, self.rd_data['source_name'], status_code=status.HTTP_201_CREATED)

    def test_upload_same_reduced_datum_twice(self):
        """
        Test that identical data raises a validation error while similar but different JSON will make it through.
        """
        self.client.post(reverse('api:reduceddatums-list'), self.rd_data, format='json')
        with self.assertRaises(ValidationError):
            self.client.post(reverse('api:reduceddatums-list'), self.rd_data, format='json')
        self.rd_data['value'] = {'magnitude': 15.582, 'filter': 'B', 'error': 0.005}
        self.client.post(reverse('api:reduceddatums-list'), self.rd_data, format='json')
        rd_queryset = ReducedDatum.objects.all()
        self.assertEqual(rd_queryset.count(), 2)

    def test_upload_reduced_datum_no_sharing_location(self):
        """
        Test that a reduced datum can be uploaded without a source_location.
        """
        del self.rd_data['source_location']
        response = self.client.post(reverse('api:reduceddatums-list'), self.rd_data, format='json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

    def test_upload_reduced_datum_no_sharing_name(self):
        """
        Test that a reduced datum can be uploaded without a source_name.
        """
        del self.rd_data['source_name']
        response = self.client.post(reverse('api:reduceddatums-list'), self.rd_data, format='json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
