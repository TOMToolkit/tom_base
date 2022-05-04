from copy import deepcopy
from unittest.mock import patch

from django.contrib.auth.models import Group, User
from django.test import override_settings
from django.urls import reverse
from django.utils import timezone
from guardian.shortcuts import assign_perm
from rest_framework import status
from rest_framework.exceptions import ValidationError
from rest_framework.test import APITestCase

from tom_observations.api_views import ObservationRecordViewSet
from tom_observations.models import ObservationGroup
from tom_observations.tests.factories import ObservingRecordFactory
from tom_targets.tests.factories import SiderealTargetFactory


@override_settings(TOM_FACILITY_CLASSES=['tom_observations.tests.utils.FakeRoboticFacility',
                                         'tom_observations.tests.utils.FakeManualFacility'],
                   TARGET_PERMISSIONS_ONLY=True)
class TestObservationViewset(APITestCase):
    def setUp(self):
        self.user = User.objects.create(username='testuser')
        self.st = SiderealTargetFactory.create(name='testtarget')
        self.st2 = SiderealTargetFactory.create(name='testtarget2')
        self.st3 = SiderealTargetFactory.create(name='testtarget3')

        self.obsr = ObservingRecordFactory.create(target_id=self.st.id, user=self.user)
        self.obsr2 = ObservingRecordFactory.create(target_id=self.st2.id)
        self.obsr3 = ObservingRecordFactory.create(target_id=self.st3.id)

        assign_perm('tom_targets.view_target', self.user, self.st2)

        self.client.force_login(self.user)

    def test_observation_detail(self):
        """Test observation API detail endpoint."""
        with self.subTest('Test that a user can view an ObservationRecord for an ObservationRecord they submitted.'):
            response = self.client.get(reverse('api:observations-detail', args=(self.obsr.id,)))
            self.assertEqual(response.json()['id'], self.obsr.id)

        with self.subTest('Test that a user can view an ObservationRecord for a target they can view.'):
            response = self.client.get(reverse('api:observations-detail', args=(self.obsr2.id,)))
            self.assertEqual(response.json()['id'], self.obsr2.id)

        with self.subTest('Test that a user cannot view an ObservationRecord for a target they cannot view.'):
            response = self.client.get(reverse('api:observations-detail', args=(self.obsr3.id,)))
            self.assertContains(response, 'Not found.', status_code=status.HTTP_404_NOT_FOUND)

    def test_observation_list(self):
        """Test observation API list endpoint."""
        response = self.client.get(reverse('api:observations-list'))
        self.assertEqual(response.json()['count'], 2)
        self.assertContains(response, f'"id":{self.obsr.id}')
        self.assertContains(response, f'"id":{self.obsr2.id}')
        self.assertNotContains(response, f'"id":{self.obsr3.id}')

    def test_observation_submit(self):
        """Test observation API submit endpoint."""
        form_data = {
            'target_id': self.st.id,
            'facility': 'FakeRoboticFacility',
            'observation_type': 'OBSERVATION',
            'observing_parameters': {
                'test_input': 'gnomes'
            }
        }
        response = self.client.post(reverse('api:observations-list'), data=form_data, follow=True)
        self.assertContains(response, 'fakeid', status_code=status.HTTP_201_CREATED)
        self.assertDictContainsSubset({'test_input': 'gnomes'}, response.json()[0]['parameters'])

    def test_observation_submit_invalid_parameters(self):
        """Test observation API submit endpoint with unsuccessful submissions."""
        form_data = {
            'target_id': self.st.id,
            'facility': 'FakeRoboticFacility',
            'observation_type': 'OBSERVATION',
            'observing_parameters': {
                'test_input': 'gnomes'
            }
        }

        required_fields = ['facility', 'observation_type', 'target_id', 'observing_parameters']
        for field_name in required_fields:
            with self.subTest('Test that all required fields return 400 if absent.'):
                missing_form_data = deepcopy(form_data)
                missing_form_data.pop(field_name)
                response = self.client.post(reverse('api:observations-list'), data=missing_form_data, follow=True)
                self.assertContains(response,
                                    f'Missing required field \'{field_name}\'.',
                                    status_code=status.HTTP_400_BAD_REQUEST)

        with self.subTest('Test that a unexpected exception returns 400.'):
            with patch('tom_observations.api_views.get_service_class') as mock_get_service_class:
                mock_get_service_class.side_effect = Exception('An error occurred.')
                response = self.client.post(reverse('api:observations-list'), data=form_data, follow=True)
                self.assertContains(response, 'An error occurred.', status_code=status.HTTP_400_BAD_REQUEST)

        with self.subTest('Test that an invalid observation form returns 400.'):
            bad_form_data = deepcopy(form_data)
            bad_form_data['observing_parameters'].pop('test_input')  # test_input is supposed to take a string
            response = self.client.post(reverse('api:observations-list'), data=bad_form_data, follow=True)
            self.assertContains(response,
                                'This field is required.',
                                status_code=status.HTTP_400_BAD_REQUEST)

    def test_observation_submit_cadence(self):
        """Test observation API submit endpoint with cadences."""
        form_data = {
            'name': 'Test Cadence',
            'target_id': self.st.id,
            'facility': 'FakeRoboticFacility',
            'observation_type': 'OBSERVATION',
            'observing_parameters': {
                'test_input': 'gnomes',
            },
            'cadence': {
                'cadence_strategy': 'ResumeCadenceAfterFailureStrategy',
                'cadence_frequency': 24,
            }
        }

        response = self.client.post(reverse('api:observations-list'), data=form_data, follow=True)
        self.assertContains(response, 'fakeid', status_code=status.HTTP_201_CREATED)
        self.assertDictContainsSubset({'name': f'{self.st.name} at FakeRoboticFacility'},
                                      response.json()[0].get('observation_groups', [])[0])
        self.assertIn(
            'ResumeCadenceAfterFailureStrategy with parameters {\'cadence_frequency\': 24}',
            response.json()[0].get('observation_groups', [])[0].get('dynamic_cadences', []))

    @patch('tom_observations.tests.utils.FakeRoboticFacility.submit_observation')
    def test_observation_multiple_records(self, mock_submit_observation):
        """Test observation API submit endpoint with multiple returned records."""
        mock_submit_observation.return_value = ['fakeid1', 'fakeid2']

        form_data = {
            'name': 'Test Multiple Records',
            'target_id': self.st.id,
            'facility': 'FakeRoboticFacility',
            'observation_type': 'OBSERVATION',
            'observing_parameters': {
                'test_input': 'gnomes',
            },
        }

        response = self.client.post(reverse('api:observations-list'), data=form_data, follow=True)
        self.assertContains(response, 'fakeid', status_code=status.HTTP_201_CREATED)
        self.assertDictContainsSubset({'name': f'{self.st.name} at FakeRoboticFacility'},
                                      response.json()[0].get('observation_groups', [])[0])

    def test_observation_submit_cadence_invalid_parameters(self):
        """Test observation API submit endpoint with cadences that are unsuccessful submissions."""
        form_data = {
            'name': 'Test Cadence',
            'target_id': self.st.id,
            'facility': 'FakeRoboticFacility',
            'observation_type': 'OBSERVATION',
            'observing_parameters': {
                'test_input': 'gnomes',
            },
            'cadence': {
                'cadence_strategy': 'ResumeCadenceAfterFailureStrategy',
                'cadence_frequency': 24,
            }
        }

        with self.subTest('Test that a missing cadence strategy returns a 400.'):
            bad_form_data = deepcopy(form_data)
            bad_form_data['cadence'].pop('cadence_strategy')
            response = self.client.post(reverse('api:observations-list'), data=bad_form_data, follow=True)
            self.assertContains(response,
                                'cadence_strategy must be included to initiate a DynamicCadence.',
                                status_code=status.HTTP_400_BAD_REQUEST)

        with self.subTest('Test that a missing cadence strategy returns a 400.'):
            bad_form_data = deepcopy(form_data)
            bad_form_data['cadence'].pop('cadence_frequency')
            response = self.client.post(reverse('api:observations-list'), data=bad_form_data, follow=True)
            self.assertContains(response,
                                'This field is required.',
                                status_code=status.HTTP_400_BAD_REQUEST)
            self.assertTrue(len(ObservationGroup.objects.all()), 0)

        with self.subTest('Test that a serializer failure returns a 400 and deletes objects.'):
            with patch.object(ObservationRecordViewSet, 'perform_create') as mock_serializer:
                mock_serializer.side_effect = ValidationError('test')
                response = self.client.post(reverse('api:observations-list'), data=form_data, follow=True)
                self.assertContains(response,
                                    'Observation submission successful, but failed to create a corresponding',
                                    status_code=status.HTTP_400_BAD_REQUEST)

    @patch('tom_observations.tests.utils.FakeRoboticFacility.get_observation_status')
    def test_observation_cancel(self, mock_get_status):
        mock_get_status.return_value = {'state': 'CANCELED',
                                        'scheduled_start': timezone.now(),
                                        'scheduled_end': timezone.now()}
        user2 = User.objects.create(username='testuser2')
        self.obsr2.facility = 'FakeRoboticFacility'
        self.obsr2.save()

        response = self.client.patch(reverse('api:observations-cancel', kwargs={'pk': self.obsr2.id}))
        self.assertContains(response, 'CANCELED')

        self.client.force_login(user2)
        response = self.client.patch(reverse('api:observations-cancel', kwargs={'pk': self.obsr2.id}))
        self.assertContains(response, 'Not found.', status_code=status.HTTP_404_NOT_FOUND)


@override_settings(TOM_FACILITY_CLASSES=['tom_observations.tests.utils.FakeRoboticFacility',
                                         'tom_observations.tests.utils.FakeManualFacility'],
                   TARGET_PERMISSIONS_ONLY=False)
class TestObservationViewsetRowLevelPermissions(APITestCase):
    def setUp(self):
        self.user = User.objects.create(username='testuser')
        self.st = SiderealTargetFactory.create(name='testtarget')

        self.obsr = ObservingRecordFactory.create(target_id=self.st.id, user=self.user, status='PENDING')
        self.obsr2 = ObservingRecordFactory.create(target_id=self.st.id, status='PENDING')
        self.obsr3 = ObservingRecordFactory.create(target_id=self.st.id, status='PENDING')

        assign_perm('tom_observations.view_observationrecord', self.user, self.obsr2)
        assign_perm('tom_observations.change_observationrecord', self.user, self.obsr2)

        self.client.force_login(self.user)

    def test_observation_list_with_permissions(self):
        """Test observation API list endpoint with row-level permissions."""
        response = self.client.get(reverse('api:observations-list'))
        self.assertEqual(response.json()['count'], 2)

    def test_observation_detail_with_permissions(self):
        """Test observation API detail endpoint with row-level permissions."""
        with self.subTest('Test that an ObservationRecord submitted by a user is visible to them.'):
            response = self.client.get(reverse('api:observations-detail', args=(self.obsr.id,)))
            self.assertEqual(response.json()['id'], self.obsr.id)

        with self.subTest('Test that a user can view an ObservationRecord for which they have permissions.'):
            response = self.client.get(reverse('api:observations-detail', args=(self.obsr2.id,)))
            self.assertEqual(response.json()['id'], self.obsr2.id)

        with self.subTest('Test that a user cannot view an ObservationRecord for which they lack permissions.'):
            response = self.client.get(reverse('api:observations-detail', args=(self.obsr3.id,)))
            self.assertContains(response, 'Not found.', status_code=status.HTTP_404_NOT_FOUND)

    def test_observation_submit_with_permissions(self):
        """Test observation API submit endpoint with groups."""
        group = Group.objects.create(name='testgroup')
        group.user_set.add(self.user)
        user2 = User.objects.create(username='testuser2')
        form_data = {
            'target_id': self.st.id,
            'facility': 'FakeRoboticFacility',
            'observation_type': 'OBSERVATION',
            'groups': [{'id': group.id}],
            'observing_parameters': {
                'test_input': 'gnomes'
            }
        }

        response = self.client.post(reverse('api:observations-list'), data=form_data, follow=True)
        self.assertContains(response, 'fakeid', status_code=status.HTTP_201_CREATED)
        self.assertDictContainsSubset({'test_input': 'gnomes'}, response.json()[0]['parameters'])

        # Test that user in testgroup can see observation
        self.client.force_login(self.user)
        response = self.client.get(reverse('api:observations-list'))
        self.assertContains(response, 'fakeid', status_code=status.HTTP_200_OK)

        # Test that user not in testgroup can't see observation
        self.client.force_login(user2)
        response = self.client.get(reverse('api:observations-list'))
        self.assertEqual(response.json()['count'], 0)

    @patch('tom_observations.tests.utils.FakeRoboticFacility.get_observation_status')
    def test_observation_cancel(self, mock_get_status):
        mock_get_status.return_value = {'state': 'CANCELED',
                                        'scheduled_start': timezone.now(),
                                        'scheduled_end': timezone.now()}
        user2 = User.objects.create(username='testuser2')
        self.obsr2.facility = 'FakeRoboticFacility'
        self.obsr2.save()

        response = self.client.patch(reverse('api:observations-cancel', kwargs={'pk': self.obsr2.id}))
        self.assertContains(response, 'CANCELED')

        self.client.force_login(user2)
        response = self.client.patch(reverse('api:observations-cancel', kwargs={'pk': self.obsr2.id}))
        self.assertContains(response, 'Not found.', status_code=status.HTTP_404_NOT_FOUND)
