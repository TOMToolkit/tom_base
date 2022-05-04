import copy

from django.contrib.auth.models import User, Group
from django.urls import reverse
from guardian.shortcuts import assign_perm, get_objects_for_user
from rest_framework import status
from rest_framework.test import APITestCase

from tom_targets.tests.factories import SiderealTargetFactory, NonSiderealTargetFactory
from tom_targets.tests.factories import TargetExtraFactory, TargetNameFactory
from tom_targets.models import Target, TargetExtra, TargetName


class TestTargetViewset(APITestCase):
    def setUp(self):
        # Create test user with permissions
        self.user = User.objects.create(username='testuser')
        self.st = SiderealTargetFactory.create(name='test target', targetextra_set=None, aliases=None)
        self.st2 = SiderealTargetFactory.create()
        self.nst = NonSiderealTargetFactory.create()
        assign_perm('tom_targets.view_target', self.user, self.st)
        assign_perm('tom_targets.view_target', self.user, self.nst)
        assign_perm('tom_targets.add_target', self.user)
        assign_perm('tom_targets.change_target', self.user, self.st)
        assign_perm('tom_targets.change_target', self.user, self.nst)
        assign_perm('tom_targets.delete_target', self.user, self.st)

        # Create test user with subset of permissions
        self.user2 = User.objects.create(username='testuser2')
        assign_perm('tom_targets.view_target', self.user2, self.st)

        # Login with privileged user
        self.client.force_login(self.user)

    def test_target_list(self):
        response = self.client.get(reverse('api:targets-list'))
        self.assertEqual(response.json()['count'], 2)

        # Ensure that a user without view_target permission on all targets can only retrieve the subset of targets for
        # which they have permission
        self.client.force_login(self.user2)
        response = self.client.get(reverse('api:targets-list'))
        self.assertEqual(response.json()['count'], 1)

    def test_target_detail(self):
        response = self.client.get(reverse('api:targets-detail', args=(self.st.id,)))
        self.assertEqual(response.json()['name'], self.st.name)

        # Ensure that a user without view_target permission cannot access the target
        self.client.force_login(self.user2)
        response = self.client.get(reverse('api:targets-detail', args=(self.nst.id,)))
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
        self.assertEqual(response.json()['detail'], 'Not found.')

    def test_target_create(self):
        collaborator = User.objects.create(username='test collaborator')
        group = Group.objects.create(name='bourgeoisie')
        group.user_set.add(self.user)
        group.user_set.add(collaborator)

        target_data = {
            'name': 'test_target_name_wtf',
            'type': Target.SIDEREAL,
            'ra': 123.456,
            'dec': -32.1,
            'groups': [
                {'id': group.id}
            ],
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
        self.assertEqual(get_objects_for_user(collaborator, 'tom_targets.view_target').first().name,
                         target_data['name'])  # Test that group permissions are respected

        # TODO: For whatever reason, in django-guardian, authenticated users have permission to create objects,
        # regardless of their row-level permissions. This should be addressed eventually--however, we don't provide a
        # way for PIs to restrict create/update ability, simply target access, so this can be ignored at present.
        #
        # self.client.force_login(self.user2)
        # target_data['name'] = 'test_target_create_bad_permissions'
        # target_data['aliases'] = []
        # response = self.client.post(reverse('api:targets-list'), data=target_data)
        # self.assertEqual(response.status_code, status.HTTP_302_FOUND)

        # Ensure targets can't be created with duplicate aliases
        invalid_target_data = copy.deepcopy(target_data)
        invalid_target_data['name'] = 'invalid_name'
        invalid_target_data['aliases'][0]['name'] = 'invalid_name'
        response = self.client.post(reverse('api:targets-list'), data=invalid_target_data)
        self.assertContains(response,
                            'Alias \'invalid_name\' conflicts with Target name \'invalid_name\'.',
                            status_code=status.HTTP_400_BAD_REQUEST)

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
        self.assertContains(response,
                            'The following fields are required for SIDEREAL targets: [\'dec\']',
                            status_code=status.HTTP_400_BAD_REQUEST)

    def test_target_create_non_sidereal_missing_parameters(self):
        target_data = {
            'name': 'test_target_name_wtf',
            'type': Target.NON_SIDEREAL,
            'epoch_of_elements': 2000,
            'inclination': '0.0005',
            'lng_asc_node': '0.12345',
            'arg_of_perihelion': '57',
            'targetextra_set': [
                {'key': 'foo', 'value': 5}
            ],
            'aliases': [
                {'name': 'alternative name'}
            ]
        }
        response = self.client.post(reverse('api:targets-list'), data=target_data)
        self.assertContains(response,
                            'The following fields are required for NON_SIDEREAL targets: [\'eccentricity\']',
                            status_code=status.HTTP_400_BAD_REQUEST)

    def test_target_update(self):
        collaborator = User.objects.create(username='test collaborator')
        group = Group.objects.create(name='bourgeoisie')
        group.user_set.add(self.user)
        group.user_set.add(collaborator)

        updates = {'ra': 123.456, 'groups': [{'id': group.id}]}
        response = self.client.patch(reverse('api:targets-detail', args=(self.st.id,)), data=updates)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.st.refresh_from_db()
        self.assertEqual(self.st.ra, updates['ra'])
        self.assertEqual(get_objects_for_user(collaborator, 'tom_targets.view_target').first().name,
                         self.st.name)  # Test that group permissions are respected

        self.client.force_login(self.user2)
        updates = {'ra': 654.321}
        response = self.client.patch(reverse('api:targets-detail', args=(self.st.id,)), data=updates)
        self.st.refresh_from_db()
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_targetname_update(self):
        # Test both create new alias and update alias
        alias = TargetNameFactory.create(name='alias', target=self.st)
        updates = {
            'aliases': [
                {'id': alias.id, 'name': 'update alias'},
                {'name': 'create alias'}
            ]
        }
        response = self.client.patch(reverse('api:targets-detail', args=(self.st.id,)), data=updates)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.st.refresh_from_db()
        alias.refresh_from_db()
        self.assertEqual(self.st.aliases.count(), 2)
        self.assertEqual(alias.name, 'update alias')

        # Ensure a user can't inadvertently update a TargetName for a different Target
        invalid_data = {
            'aliases': [
                {'id': alias.id, 'name': 'alias for wrong target'}
            ]
        }
        response = self.client.patch(reverse('api:targets-detail', args=(self.nst.id,)), data=invalid_data)
        self.assertContains(response,
                            f'TargetName identified by id \'{alias.id}\' is not an',
                            status_code=status.HTTP_400_BAD_REQUEST)

        # Ensure proper exception handling when updating or creating with the same name
        updates = {
            'aliases': [
                {'name': self.st.name}
            ]
        }
        response = self.client.patch(reverse('api:targets-detail', args=(self.st.id,)), data=updates)
        self.assertContains(response,
                            f'Alias \'{self.st.name}\' conflicts with Target name \'{self.st.name}\'',
                            status_code=status.HTTP_400_BAD_REQUEST)

    def test_target_delete(self):
        response = self.client.delete(reverse('api:targets-detail', args=(self.st.id,)))
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        self.assertFalse(Target.objects.filter(pk=self.st.id).exists())

        self.client.force_login(self.user2)
        response = self.client.delete(reverse('api:targets-detail', args=(self.nst.id,)))
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)


class TestTargetNameViewset(APITestCase):
    def setUp(self):
        user = User.objects.create(username='testuser')
        self.st = SiderealTargetFactory.create()
        self.alias = TargetNameFactory.create(target=self.st)
        assign_perm('tom_targets.view_target', user, self.st)
        assign_perm('tom_targets.delete_target', user, self.st)

        self.user2 = User.objects.create(username='testuser2')

        self.client.force_login(user)

    def test_targetname_detail(self):
        response = self.client.get(reverse('api:targetname-detail', args=(self.alias.id,)))
        self.assertEqual(response.json()['name'], self.alias.name)

        # Ensure that a user without view_target permission cannot access the target name
        self.client.force_login(self.user2)
        response = self.client.get(reverse('api:targetname-detail', args=(self.alias.id,)))
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_targetname_delete(self):
        response = self.client.delete(reverse('api:targetname-detail', args=(self.alias.id,)))
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        self.assertFalse(TargetName.objects.filter(pk=self.alias.id).exists())


class TestTargetExtraViewset(APITestCase):
    def setUp(self):
        user = User.objects.create(username='testuser')
        self.st = SiderealTargetFactory.create()
        self.extra = TargetExtraFactory.create(target=self.st)
        assign_perm('tom_targets.view_target', user, self.st)
        assign_perm('tom_targets.delete_target', user, self.st)

        self.user2 = User.objects.create(username='testuser2')

        self.client.force_login(user)

    def test_targetextra_detail(self):
        response = self.client.get(reverse('api:targetextra-detail', args=(self.extra.id,)))
        self.assertEqual(response.json()['id'], self.extra.id)

        # Ensure that a user without view_target permission cannot access the target extra
        self.client.force_login(self.user2)
        response = self.client.get(reverse('api:targetextra-detail', args=(self.extra.id,)))
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_targetextra_delete(self):
        response = self.client.delete(reverse('api:targetextra-detail', args=(self.extra.id,)))
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        self.assertFalse(TargetExtra.objects.filter(pk=self.extra.id).exists())
