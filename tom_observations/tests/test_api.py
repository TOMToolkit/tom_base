from unittest.mock import patch

from django.contrib.auth.models import User, Group
from django.test import override_settings
from django.urls import reverse
from guardian.shortcuts import assign_perm, get_objects_for_user
from rest_framework import status
from rest_framework.test import APITestCase

from tom_observations.tests.factories import ObservingRecordFactory
from tom_observations.models import ObservationRecord
from tom_targets.tests.factories import SiderealTargetFactory, NonSiderealTargetFactory
from tom_targets.tests.factories import TargetExtraFactory, TargetNameFactory
from tom_targets.models import Target, TargetExtra, TargetName


@override_settings(TOM_FACILITY_CLASSES=['tom_observations.tests.utils.FakeRoboticFacility',
                                         'tom_observations.tests.utils.FakeManualFacility'])
class TestObservationViewset(APITestCase):
    def setUp(self):
        self.user = User.objects.create(username='testuser')
        self.st = SiderealTargetFactory.create(name='testtarget')
        self.st2 = SiderealTargetFactory.create(name='testtarget2')

        self.obsr = ObservingRecordFactory.create(target_id=self.st.id, user=self.user)
        self.obsr2 = ObservingRecordFactory.create(target_id=self.st.id)
        self.obsr3 = ObservingRecordFactory.create(target_id=self.st2.id)

        assign_perm('tom_targets.view_target', self.user, self.st)

        self.client.force_login(self.user)

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
        print(response.content)

    # @patch('tom_observations.tests.utils.FakeRoboticFacility.submit_observation')
    def test_observation_submit_cadence(self):
        # mock_submit_observation.return_value = ['fakeid1', 'fakeid2']

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
        print(response.json())
        self.assertDictContainsSubset(
            {'cadence_strategy': 'ResumeCadenceAfterFailureStrategy'},
            response.json()[0].get('observationgroup_set', [])[0].get('dyanmiccadence_set', []))
