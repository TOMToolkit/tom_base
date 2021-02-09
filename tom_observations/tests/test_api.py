from copy import deepcopy
from unittest.mock import MagicMock, patch

from django.contrib.auth.models import User, Group
from django.test import override_settings
from django.urls import reverse
from guardian.shortcuts import assign_perm, get_objects_for_user
from rest_framework import status
from rest_framework.exceptions import ValidationError
from rest_framework.test import APITestCase

from tom_observations.api_views import ObservationRecordViewSet
from tom_observations.models import DynamicCadence, ObservationGroup, ObservationRecord
from tom_observations.tests.factories import ObservingRecordFactory
from tom_targets.models import Target, TargetExtra, TargetName
from tom_targets.tests.factories import NonSiderealTargetFactory, SiderealTargetFactory
from tom_targets.tests.factories import TargetExtraFactory, TargetNameFactory


@override_settings(TOM_FACILITY_CLASSES=['tom_observations.tests.utils.FakeRoboticFacility',
                                         'tom_observations.tests.utils.FakeManualFacility'])
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
        response = self.client.get(reverse('api:observations-list'))
        self.assertEqual(response.json()['count'], 2)
        self.assertContains(response, f'"id":{self.obsr.id}')
        self.assertContains(response, f'"id":{self.obsr2.id}')
        self.assertNotContains(response, f'"id":{self.obsr3.id}')

    def test_observation_submit(self):
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
                                    status_code=status.HTTP_400_BAD_REQUEST)  # TODO: should this be a 400 or 500?


@override_settings(TARGET_PERMISSIONS_ONLY=False)
class TestObservationViewsetRowLevelPermissions(APITestCase):
    def setUp(self):
        self.user = User.objects.create(username='testuser')
        self.st = SiderealTargetFactory.create(name='testtarget')

        self.obsr = ObservingRecordFactory.create(target_id=self.st.id, user=self.user)
        self.obsr2 = ObservingRecordFactory.create(target_id=self.st.id)
        self.obsr3 = ObservingRecordFactory.create(target_id=self.st.id)

        assign_perm('tom_observations.view_observationrecord', self.user, self.obsr2)

        self.client.force_login(self.user)

    def test_observation_list_with_permissions(self):
        response = self.client.get(reverse('api:observations-list'))
        self.assertEqual(response.json()['count'], 2)

    def test_observation_detail_with_permissions(self):
        with self.subTest('Test that an ObservationRecord submitted by a user is visible to them.'):
            response = self.client.get(reverse('api:observations-detail', args=(self.obsr.id,)))
            self.assertEqual(response.json()['id'], self.obsr.id)

        with self.subTest('Test that a user can view an ObservationRecord for which they have permissions.'):
            response = self.client.get(reverse('api:observations-detail', args=(self.obsr2.id,)))
            self.assertEqual(response.json()['id'], self.obsr2.id)

        with self.subTest('Test that a user cannot view an ObservationRecord for which they lack permissions.'):
            response = self.client.get(reverse('api:observations-detail', args=(self.obsr3.id,)))
            self.assertContains(response, 'Not found.', status_code=status.HTTP_404_NOT_FOUND)
