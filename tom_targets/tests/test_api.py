from rest_framework.test import APITestCase
from rest_framework import status
from guardian.shortcuts import assign_perm
from django.urls import reverse
from django.contrib.auth.models import User

from tom_targets.models import Target
from .factories import SiderealTargetFactory, NonSiderealTargetFactory


class TestTargetViewset(APITestCase):
    def setUp(self):
        self.user = User.objects.create(username='testuser')
        self.user2 = User.objects.create(username='testuser2')
        # self.client.force_login(user)
        self.st = SiderealTargetFactory.create()
        self.nst = NonSiderealTargetFactory.create()
        assign_perm('tom_targets.view_target', self.user, self.st)
        assign_perm('tom_targets.add_target', self.user, self.st)
        assign_perm('tom_targets.change_target', self.user, self.st)
        assign_perm('tom_targets.delete_target', self.user, self.st)
        assign_perm('tom_targets.view_target', self.user, self.nst)
        assign_perm('tom_targets.view_target', self.user2, self.st)

    def test_target_list(self):
        self.client.force_login(self.user)
        response = self.client.get(reverse('api:targets-list'))
        self.assertEqual(response.json()['count'], 2)

        # Ensure that a user without view_target permission on all targets can only retrieve the subset of targets for 
        # which they have permission
        self.client.force_login(self.user2)
        response = self.client.get(reverse('api:targets-list'))
        self.assertEqual(response.json()['count'], 1)

    def test_target_detail(self):
        self.client.force_login(self.user)
        response = self.client.get(reverse('api:targets-detail', args=(self.st.id,)))
        self.assertEqual(response.json()['name'], self.st.name)

        # Ensure that a user without view_target permission cannot access the target
        self.client.force_login(self.user2)
        response = self.client.get(reverse('api:targets-detail', args=(self.nst.id,)))
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
        self.client.force_login(self.user)
        response = self.client.post(reverse('api:targets-list'), data=target_data)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.json()['name'], target_data['name'])
        self.assertEqual(response.json()['aliases'][0]['name'], target_data['aliases'][0]['name'])

        # self.client.force_login(self.user2)
        # target_data['name'] = 'test_target_create_bad_permissions'
        # response = self.client.post(reverse('api:targets-list'), data=target_data)
        # self.assertEqual(response.status_code, status.HTTP_302_REDIRECT)

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
        self.client.force_login(self.user)
        updates = {'ra': 123.456}
        response = self.client.patch(reverse('api:targets-detail', args=(self.st.id,)), data=updates, follow=True)
        print(response.content)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.st.refresh_from_db()
        self.assertEqual(self.st.ra, updates['ra'])

        # self.client.force_login(self.user2)
        # updates = {'ra': 654.321}
        # response = self.client.patch(reverse('api:targets-detail', args=(self.st.id,)), data=updates)
        # self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_target_delete(self):
        response = self.client.delete(reverse('api:targets-detail', args=(self.st.id,)))
        print(response.content)
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        self.assertFalse(Target.objects.filter(pk=self.st.id).exists())


class TestTargetDetailAPIView(APITestCase):
    def setUp(self):
        user = User.objects.create(username='testuser')
        self.client.force_login(user)
        self.st = SiderealTargetFactory.create()
        self.nst = NonSiderealTargetFactory.create()
        assign_perm('tom_targets.view_target', user, self.st)
        assign_perm('tom_targets.view_target', user, self.nst)