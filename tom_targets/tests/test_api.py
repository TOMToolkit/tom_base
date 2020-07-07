from rest_framework.test import APITestCase
from rest_framework import status
from guardian.shortcuts import assign_perm
from django.urls import reverse
from django.contrib.auth.models import User

from tom_targets.models import Target
from .factories import SiderealTargetFactory, NonSiderealTargetFactory


class TestTargetViewset(APITestCase):
    def setUp(self):
        user = User.objects.create(username='testuser')
        self.client.force_login(user)
        self.st = SiderealTargetFactory.create()
        self.nst = NonSiderealTargetFactory.create()
        assign_perm('tom_targets.view_target', user, self.st)
        assign_perm('tom_targets.view_target', user, self.nst)

    def test_target_list(self):
        response = self.client.get(reverse('api:targets-list'))
        self.assertEqual(response.json()['count'], 2)

    def test_target_detail(self):
        response = self.client.get(reverse('api:targets-detail', args=(self.st.id,)))
        self.assertEqual(response.json()['name'], self.st.name)

    def test_target_detail_bad_permissions(self):
        other_user = User.objects.create(username='otheruser')
        self.client.force_login(other_user)
        response = self.client.get(reverse('api:targets-detail', args=(self.st.id,)), follow=True)
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
        self.assertEqual(response.json()['detail'], 'Not found.')

    def test_target_create(self):
        target_data = {
            'name': 'test_target_name_wtf',
            'type': Target.SIDEREAL,
            'ra': 123.456,
            'dec': -32.1,
            'targetextra_set': [
                {'key': 'foo', 'value': 5}
            ],
            'aliases': [
                {'name': 'alternative name'}
            ]
        }
        response = self.client.post(reverse('api:targets-list'), data=target_data)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.json()['name'], target_data['name'])
        self.assertEqual(response.json()['aliases'][0]['name'], target_data['aliases'][0]['name'])

    def test_target_create_sidereal_missing_parameters(self):
        target_data = {
            'name': 'test_target_name_wtf',
            'type': Target.SIDEREAL,
            'ra': 123.456,
            'targetextra_set': [
                {'key': 'foo', 'value': 5}
            ],
            'aliases': [
                {'name': 'alternative name'}
            ]
        }
        response = self.client.post(reverse('api:targets-list'), data=target_data)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(response.json()['name'], target_data['name'])
        self.assertEqual(response.json()['aliases'][0]['name'], target_data['aliases'][0]['name'])

    def test_target_create_non_sidereal_missing_parameters(self):
        target_data = {
            'name': 'test_target_name_wtf',
            'type': Target.SIDEREAL,
            'ra': 123.456,
            'dec': -32.1,
            'targetextra_set': [
                {'key': 'foo', 'value': 5}
            ],
            'aliases': [
                {'name': 'alternative name'}
            ]
        }
        response = self.client.post(reverse('api:targets-list'), data=target_data)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.json()['name'], target_data['name'])
        self.assertEqual(response.json()['aliases'][0]['name'], target_data['aliases'][0]['name'])

    def test_target_update(self):
        updates = {'ra': 123.456}
        response = self.client.patch(reverse('api:targets-detail', args=(self.st.id,)), data=updates)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.st.refresh_from_db()
        self.assertEqual(self.st.ra, updates['ra'])

    def test_target_delete(self):
        response = self.client.delete(reverse('api:targets-detail', args=(self.st.id,)))
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        self.assertFalse(Target.objects.filter(pk=self.st.id).exists())
