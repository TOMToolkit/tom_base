from datetime import datetime, timedelta
from unittest import mock

from django.contrib.auth.models import User
from django.contrib.messages import get_messages
from django.forms import ValidationError
from django.test import TestCase, override_settings
from django.urls import reverse

from astroplan import FixedTarget
from astropy.coordinates import get_sun, SkyCoord
from astropy.time import Time

from .factories import ObservingRecordFactory, ObservationTemplateFactory, SiderealTargetFactory, TargetNameFactory
from tom_observations.utils import get_astroplan_sun_and_time, get_sidereal_visibility
from tom_observations.tests.utils import FakeRoboticFacility
from tom_observations.models import ObservationRecord, ObservationGroup, ObservationTemplate
from tom_targets.models import Target
from guardian.shortcuts import assign_perm


@override_settings(TOM_FACILITY_CLASSES=['tom_observations.tests.utils.FakeRoboticFacility'],
                   TARGET_PERMISSIONS_ONLY=True)
class TestObservationViews(TestCase):
    def setUp(self):
        self.target = SiderealTargetFactory.create()
        self.target_name = TargetNameFactory.create(target=self.target)
        self.observation_record = ObservingRecordFactory.create(
            target_id=self.target.id,
            facility=FakeRoboticFacility.name,
            parameters={}
        )
        self.user = User.objects.create_user(username='vincent_adultman', password='important')
        self.user2 = User.objects.create_user(username='peon', password='plebian')
        assign_perm('tom_targets.view_target', self.user, self.target)
        self.client.force_login(self.user)

    def test_observation_list(self):
        response = self.client.get(reverse('tom_observations:list'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(
            response, reverse('tom_observations:detail', kwargs={'pk': self.observation_record.id})
        )

    def test_observation_list_unauthorized(self):
        self.client.force_login(self.user2)
        response = self.client.get(reverse('tom_observations:list'))
        self.assertEqual(response.status_code,  200)
        self.assertNotContains(
            response, reverse('tom_observations:detail', kwargs={'pk': self.observation_record.id})
        )

    def test_observation_detail(self):
        response = self.client.get(
            reverse('tom_observations:detail', kwargs={'pk': self.observation_record.id})
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(
            response, FakeRoboticFacility().get_observation_url(self.observation_record.observation_id)
        )

    def test_observation_detail_unauthorized(self):
        self.client.force_login(self.user2)
        response = self.client.get(
            reverse('tom_observations:detail', kwargs={'pk': self.observation_record.id})
        )
        self.assertEqual(response.status_code, 404)

    def test_update_observations(self):
        response = self.client.get(reverse('tom_observations:list') + '?update_status=True', follow=True)
        self.assertContains(response, 'COMPLETED', status_code=200)

    def test_update_observations_not_authenticated(self):
        """Test that an unauthenticated user is redirected to login screen if they attempt to update observations."""
        response = self.client.get(reverse('tom_observations:list') + '?update_status=True')
        self.assertEqual(response.status_code, 302)

    def test_get_observation_form(self):
        url = f"{reverse('tom_observations:create', kwargs={'facility': 'FakeRoboticFacility'})}" \
              f"?target_id={self.target.id}&observation_type=OBSERVATION"
        response = self.client.get(url)
        # self.assertContains(response, 'fake form input')
        self.assertContains(response, 'FakeRoboticFacility')

    def test_add_observations_to_group(self):
        obs_group = ObservationGroup.objects.create(name='testgroup')
        reqstring = '?action=add&selected={}&observationgroup={}'.format(
            self.observation_record.id,
            obs_group.id
        )
        response = self.client.get(reverse('tom_observations:list') + reqstring)
        self.assertEqual(response.status_code, 302)
        obs_group.refresh_from_db()
        self.assertIn(self.observation_record, obs_group.observation_records.all())

    def test_remove_observations_from_group(self):
        obs_group = ObservationGroup.objects.create(name='testgroup')
        obs_group.observation_records.add(self.observation_record)
        obs_group.save()
        self.assertIn(self.observation_record, obs_group.observation_records.all())
        reqstring = '?action=remove&selected={}&observationgroup={}'.format(
            self.observation_record.id,
            obs_group.id
        )
        response = self.client.get(reverse('tom_observations:list') + reqstring)
        self.assertEqual(response.status_code, 302)
        obs_group.refresh_from_db()
        self.assertNotIn(self.observation_record, obs_group.observation_records.all())


@override_settings(TOM_FACILITY_CLASSES=['tom_observations.tests.utils.FakeRoboticFacility',
                                         'tom_observations.tests.utils.FakeManualFacility'],
                   TARGET_PERMISSIONS_ONLY=True)
class TestObservationCreateView(TestCase):
    def setUp(self):
        self.target = SiderealTargetFactory.create()
        self.target_name = TargetNameFactory.create(target=self.target)
        self.observation_record = ObservingRecordFactory.create(
            target_id=self.target.id,
            facility=FakeRoboticFacility.name,
            parameters={}
        )
        self.user = User.objects.create_user(username='vincent_adultman', password='important')
        self.user2 = User.objects.create_user(username='peon', password='plebian')
        assign_perm('tom_targets.view_target', self.user, self.target)
        self.client.force_login(self.user)

    def test_submit_observation_robotic(self):
        form_data = {
            'target_id': self.target.id,
            'test_input': 'gnomes',
            'facility': 'FakeRoboticFacility',
            'observation_type': 'OBSERVATION'
        }
        self.client.post(
            '{}?target_id={}'.format(
                reverse('tom_observations:create', kwargs={'facility': 'FakeRoboticFacility'}),
                self.target.id
            ),
            data=form_data,
            follow=True
        )
        self.assertTrue(ObservationRecord.objects.filter(observation_id='fakeid').exists())
        self.assertEqual(ObservationRecord.objects.filter(observation_id='fakeid').first().user, self.user)

    # TODO: this test
    # def test_submit_observation_cadence(self):
    #     form_data = {
    #         'target_id': self.target.id,
    #         'test_input': 'gnomes',
    #         'facility': 'FakeRoboticFacility',
    #         'observation_type': 'OBSERVATION',
    #         'cadence_strategy': 'RetryFailedObservationsStrategy',
    #         'cadence_frequency': 24,
    #     }

    def test_submit_observation_manual(self):
        form_data = {
            'target_id': self.target.id,
            'test_input': 'elves',
            'facility': 'FakeManualFacility',
        }
        url = f"{reverse('tom_observations:create', kwargs={'facility': 'FakeManualFacility'})}" \
              f"?target_id={self.target.id}"
        self.client.post(url, data=form_data, follow=True)
        self.assertTrue(ObservationRecord.objects.filter(observation_id='fakeid').exists())
        self.assertEqual(ObservationRecord.objects.filter(observation_id='fakeid').first().user, self.user)


@override_settings(TOM_FACILITY_CLASSES=['tom_observations.tests.utils.FakeRoboticFacility'],
                   TARGET_PERMISSIONS_ONLY=True)
class TestObservationCancelView(TestCase):
    def setUp(self):
        self.target = SiderealTargetFactory.create()
        self.observation_record = ObservingRecordFactory.create(
            target_id=self.target.id,
            facility=FakeRoboticFacility.name,
            parameters={},
            status='PENDING'
        )
        self.user = User.objects.create_user(username='vincent_adultman', password='important')
        self.client.force_login(self.user)

    @mock.patch('tom_observations.tests.utils.FakeRoboticFacility.get_observation_status')
    def test_cancel_observation(self, mock_get_status):
        mock_get_status.return_value = {'state': 'CANCELED',
                                        'scheduled_start': datetime.now(),
                                        'scheduled_end': datetime.now()}
        self.observation_record.status = 'PENDING'
        self.observation_record.save()

        self.client.get(reverse('tom_observations:cancel', kwargs={'pk': self.observation_record.id}))
        self.observation_record.refresh_from_db()
        self.assertEqual(self.observation_record.status, 'CANCELED')

    @mock.patch('tom_observations.tests.utils.FakeRoboticFacility.cancel_observation')
    def test_cancel_observation_failure(self, mock_cancel_observation):
        mock_cancel_observation.return_value = False
        response = self.client.get(reverse('tom_observations:cancel', kwargs={'pk': self.observation_record.id}))

        messages = [(m.message, m.level) for m in get_messages(response.wsgi_request)]
        self.assertEqual(messages[0][0], 'Unable to cancel observation.')

    @mock.patch('tom_observations.tests.utils.FakeRoboticFacility.cancel_observation')
    def test_cancel_observation_exception(self, mock_cancel_observation):
        mock_cancel_observation.side_effect = ValidationError('mock error')
        response = self.client.get(reverse('tom_observations:cancel', kwargs={'pk': self.observation_record.id}))

        messages = [(m.message, m.level) for m in get_messages(response.wsgi_request)]
        self.assertEqual(messages[0][0], 'Unable to cancel observation: [\'mock error\']')


@override_settings(TOM_FACILITY_CLASSES=['tom_observations.tests.utils.FakeRoboticFacility'],
                   TARGET_PERMISSIONS_ONLY=True)
class TestAddExistingObservationView(TestCase):
    def setUp(self):
        self.target = SiderealTargetFactory.create()
        self.user = User.objects.create_user(username='vincent_adultman', password='important')
        self.client.force_login(self.user)

    def test_add_existing_observation(self):
        form_data = {
            'facility': 'FakeRoboticFacility',
            'target_id': self.target.id,
            'observation_id': '1234567890'
        }
        response = self.client.post(reverse('tom_observations:add-existing'), data=form_data, follow=True)

        messages = [(m.message, m.level) for m in get_messages(response.wsgi_request)]
        self.assertEqual(messages[0][0], 'Successfully associated observation record 1234567890')

        self.assertTrue(ObservationRecord.objects.filter(observation_id=form_data['observation_id']).exists())

    def test_add_existing_observation_duplicate(self):
        obsr = ObservingRecordFactory.create(
            target_id=self.target.id,
            facility=FakeRoboticFacility.name,
            parameters={},
            observation_id='1234567890'
        )

        form_data = {
            'facility': 'FakeRoboticFacility',
            'target_id': self.target.id,
            'observation_id': obsr.observation_id
        }
        response = self.client.post(reverse('tom_observations:add-existing'), data=form_data, follow=True)
        self.assertContains(response,
                            'An observation record already exists in your TOM for this combination')
        self.assertEqual(ObservationRecord.objects.filter(observation_id=obsr.observation_id).count(), 1)

        form_data['confirm'] = True
        response = self.client.post(reverse('tom_observations:add-existing'), data=form_data, follow=True)
        messages = [(m.message, m.level) for m in get_messages(response.wsgi_request)]
        self.assertEqual(messages[0][0], f'Successfully associated observation record {obsr.observation_id}')

        self.assertEqual(ObservationRecord.objects.filter(observation_id=obsr.observation_id).count(), 2)


@override_settings(TOM_FACILITY_CLASSES=['tom_observations.tests.utils.FakeRoboticFacility'],
                   TARGET_PERMISSIONS_ONLY=False)
class TestObservationViewsRowLevelPermissions(TestCase):
    def setUp(self):
        self.target = SiderealTargetFactory.create()
        self.target_name = TargetNameFactory.create(target=self.target)
        self.observation_record = ObservingRecordFactory.create(
            target_id=self.target.id,
            facility=FakeRoboticFacility.name,
            parameters={}
        )
        user = User.objects.create_user(username='vincent_adultman', password='important')
        self.user2 = User.objects.create_user(username='peon', password='plebian')
        assign_perm('tom_targets.view_target', user, self.target)
        assign_perm('tom_targets.view_target', self.user2, self.target)
        assign_perm('tom_observations.view_observationrecord', user, self.observation_record)
        self.client.force_login(user)

    def test_observation_list_authorized(self):
        response = self.client.get(reverse('tom_observations:list'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(
            response, reverse('tom_observations:detail', kwargs={'pk': self.observation_record.id})
        )

    def test_observation_list_unauthorized(self):
        self.client.force_login(self.user2)
        response = self.client.get(reverse('tom_observations:list'))
        self.assertEqual(response.status_code, 200)
        self.assertNotContains(
            response, reverse('tom_observations:detail', kwargs={'pk': self.observation_record.id})
        )

    def test_observation_detail(self):
        response = self.client.get(
            reverse('tom_observations:detail', kwargs={'pk': self.observation_record.id})
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(
            response, FakeRoboticFacility().get_observation_url(self.observation_record.observation_id)
        )

    def test_observation_detail_unauthorized(self):
        self.client.force_login(self.user2)
        response = self.client.get(
            reverse('tom_observations:detail', kwargs={'pk': self.observation_record.id})
        )
        self.assertEqual(response.status_code, 404)


@override_settings(TOM_FACILITY_CLASSES=['tom_observations.tests.utils.FakeRoboticFacility'])
class TestObservationGroupViews(TestCase):
    pass


@override_settings(TOM_FACILITY_CLASSES=['tom_observations.tests.utils.FakeRoboticFacility'])
class TestObservationTemplateViews(TestCase):
    def setUp(self):
        self.observation_template = ObservationTemplateFactory.create(name='Test Template')
        self.user = User.objects.create_user(username='test', password='test')
        self.client.force_login(self.user)

    def test_observation_template_list(self):
        response = self.client.get(reverse('tom_observations:template-list'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(
            response, reverse('tom_observations:template-update', kwargs={'pk': self.observation_template.id})
        )

    def test_observation_template_create(self):
        response = self.client.get(reverse('tom_observations:template-create',
                                           kwargs={'facility': 'FakeRoboticFacility'}))
        self.assertContains(response, 'Template name')

    def test_observation_template_delete(self):
        response = self.client.post(reverse('tom_observations:template-delete',
                                    args=(self.observation_template.id,)),
                                    follow=True)
        self.assertRedirects(response, reverse('tom_observations:template-list'), status_code=302)
        self.assertFalse(ObservationTemplate.objects.filter(pk=self.observation_template.id).exists())


class TestUpdatingObservations(TestCase):
    def setUp(self):
        self.t1 = SiderealTargetFactory.create()
        self.or1 = ObservingRecordFactory.create(target_id=self.t1.id, facility='FakeRoboticFacility', status='PENDING')
        self.or2 = ObservingRecordFactory.create(target_id=self.t1.id, status='COMPLETED')
        self.or3 = ObservingRecordFactory.create(target_id=self.t1.id, facility='FakeRoboticFacility', status='PENDING')
        self.t2 = SiderealTargetFactory.create()
        self.or4 = ObservingRecordFactory.create(target_id=self.t2.id, status='PENDING')

    # Tests that only 2 of the three created observing records are updated, as
    # the third is in a completed state
    def test_update_all_observations_for_facility(self):
        with mock.patch.object(FakeRoboticFacility, 'update_observation_status') as uos_mock:
            FakeRoboticFacility().update_all_observation_statuses()
            self.assertEquals(uos_mock.call_count, 2)

    # Tests that only the observing records associated with the given target are updated
    def test_update_individual_target_observations_for_facility(self):
        with mock.patch.object(FakeRoboticFacility, 'update_observation_status', return_value='COMPLETED') as uos_mock:
            FakeRoboticFacility().update_all_observation_statuses(target=self.t1)
            self.assertEquals(uos_mock.call_count, 2)


class TestGetVisibility(TestCase):
    def setUp(self):
        self.sun = get_sun(Time(datetime(2019, 10, 9, 13, 56)))
        self.target = Target(
            ra=(self.sun.ra.deg + 180) % 360,
            dec=-(self.sun.dec.deg),
            type=Target.SIDEREAL
        )
        self.start = datetime(2018, 10, 9, 13, 56, 16)
        self.interval = 10
        self.airmass_limit = 10

    def test_get_astroplan_sun_and_time(self):
        end = self.start + timedelta(days=2)
        sun, time_range = get_astroplan_sun_and_time(self.start, end, self.interval)
        self.assertIsInstance(sun, SkyCoord)
        self.assertEqual(len(time_range), 288)
        check_time_range = [time.mjd for time in time_range[::50]]
        expected_time_range = [58400.58074074052, 58400.92796296533,
                               58401.27518519014, 58401.62240741495,
                               58401.96962963976, 58402.31685186457]
        for i, value in enumerate(expected_time_range):
            self.assertEqual(check_time_range[i], value)

    def test_get_astroplan_sun_and_time_small_range(self):
        end = self.start + timedelta(hours=10)
        sun, time_range = get_astroplan_sun_and_time(self.start, end, self.interval)
        self.assertIsInstance(sun, FixedTarget)
        self.assertEqual(len(time_range), 61)
        check_time_range = [time.mjd for time in time_range[::20]]
        expected_time_range = [58400.58074074052, 58400.71962963045,
                               58400.85851852037, 58400.997407410294]
        for i, value in enumerate(expected_time_range):
            self.assertEqual(check_time_range[i], value)

    def test_get_visibility_invalid_target_type(self):
        invalid_target = self.target
        invalid_target.type = 'Invalid Type'
        end = self.start + timedelta(minutes=60)
        airmass = get_sidereal_visibility(invalid_target, self.start, end, self.interval, self.airmass_limit)
        self.assertEqual(len(airmass), 0)

    def test_get_visibility_invalid_params(self):
        self.assertRaisesRegex(
            Exception, 'Start must be before end', get_sidereal_visibility,
            self.target, datetime(2018, 10, 10), datetime(2018, 10, 9),
            self.interval, self.airmass_limit
        )

    @mock.patch('tom_observations.utils.facility.get_service_classes')
    def test_get_visibility_sidereal(self, mock_facility):
        mock_facility.return_value = {'Fake Robotic Facility': FakeRoboticFacility}
        end = self.start + timedelta(minutes=60)
        airmass = get_sidereal_visibility(self.target, self.start, end, self.interval, self.airmass_limit)
        airmass_data = airmass['(Fake Robotic Facility) Siding Spring'][1]
        expected_airmass = [
            1.2619096566629477, 1.2648181328558852, 1.2703522349950636, 1.2785703053923894,
            1.2895601364316183, 1.3034413026227516, 1.3203684217446099
        ]
        self.assertEqual(len(airmass_data), len(expected_airmass))
        for i in range(0, len(expected_airmass)):
            self.assertAlmostEqual(airmass_data[i], expected_airmass[i], places=3)
