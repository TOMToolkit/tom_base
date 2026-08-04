from tom_targets.base_models import get_target_model_app_label
from datetime import datetime, timedelta
from http import HTTPStatus
from unittest import mock

from django.contrib.auth.models import User
from django.contrib.messages import get_messages
from django.forms import ValidationError
from django.template.loader import render_to_string
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from astroplan import FixedTarget
from astropy.coordinates import get_sun, SkyCoord
from astropy.time import Time

from .factories import ObservingRecordFactory, ObservationTemplateFactory, SiderealTargetFactory, TargetNameFactory
from tom_observations.facility import get_service_classes
from tom_observations.templatetags.observation_extras import observation_facilities_list
from tom_observations.utils import get_astroplan_sun_and_time, get_sidereal_visibility
from tom_observations.tests.utils import FakeManualFacility, FakeRoboticFacility
from tom_observations.models import ObservationRecord, ObservationGroup, ObservationTemplate
from tom_targets.models import Target
from guardian.shortcuts import assign_perm


@override_settings(TOM_FACILITY_CLASSES=['tom_observations.tests.utils.FakeRoboticFacility'],
                   TARGET_PERMISSIONS_ONLY=True)
class TestObservationViews(TestCase):
    def setUp(self):
        self.target = SiderealTargetFactory.create()
        self.target2 = SiderealTargetFactory.create()
        self.target_name = TargetNameFactory.create(target=self.target)
        self.observation_record = ObservingRecordFactory.create(
            target_id=self.target.id,
            facility=FakeRoboticFacility.name,
            parameters={}
        )
        self.user = User.objects.create_user(username='vincent_adultman', password='important')
        self.user2 = User.objects.create_user(username='peon', password='plebian')
        target_app_label = get_target_model_app_label()
        assign_perm(f'{target_app_label}.view_target', self.user, self.target)
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

    def test_update_observations_two_observation(self):
        """Test that updating observations doesn't crash for multiple targets with the same observation ID."""
        ObservingRecordFactory.create(
            facility=FakeRoboticFacility.name,
            target_id=self.target2.id,
            observation_id=self.observation_record.observation_id,
            parameters={}
        )
        response = self.client.get(reverse('tom_observations:list') + '?update_status=True', follow=True)
        self.assertContains(response, 'COMPLETED', status_code=200)

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
        target_app_label = get_target_model_app_label()
        assign_perm(f'{target_app_label}.view_target', self.user, self.target)
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

    @mock.patch('tom_observations.tests.utils.FakeRoboticFacility.set_user')
    def test_submit_observation_robotic_gets_user(self, mock_method):
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
        calls = [mock.call(self.user)]
        mock_method.assert_has_calls(calls)

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
                                        'scheduled_start': timezone.now(),
                                        'scheduled_end': timezone.now()}
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
        self.target = SiderealTargetFactory.create(permissions='PUBLIC')
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
class TestCallbackView(TestCase):
    def setUp(self):
        self.target = SiderealTargetFactory.create(permissions='PUBLIC')
        self.user = User.objects.create_user(username='vincent_adultman', password='important')
        self.client.force_login(self.user)

    def test_callback(self):
        """

        The callback url is constructed by the OCS and the user is redirected to it after
        the observation record is created. This tests that a corresponding ObvservationRecord is created
        on the TOM side, just as if one was created using the built-in OCS form.
        The view should redirect the user to the detail view of the observation record.
        """
        callback_params = f"?target_id={self.target.id}&facility=FakeRoboticFacility&observation_id=1234"
        url = reverse('tom_observations:callback') + callback_params
        response = self.client.get(url)
        observation = ObservationRecord.objects.get(target=self.target, facility='FakeRoboticFacility')
        group = observation.observationgroup_set.first()
        self.assertRedirects(response, reverse('tom_observations:list') + f"?observationgroup={group.id}")


@override_settings(TOM_FACILITY_CLASSES=['tom_observations.tests.utils.FakeRoboticFacility'])
class TestFacilityStatusView(TestCase):
    def setUp(self):
        pass

    def test_facility_status(self):
        response = self.client.get(
            reverse('tom_observations:render-facility-status-list'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'coj.domb.1m0a', status_code=HTTPStatus.OK)


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
        target_app_label = get_target_model_app_label()
        assign_perm(f'{target_app_label}.view_target', user, self.target)
        assign_perm(f'{target_app_label}.view_target', self.user2, self.target)
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
            self.assertEqual(uos_mock.call_count, 2)

    # Tests that only the observing records associated with the given target are updated
    def test_update_individual_target_observations_for_facility(self):
        with mock.patch.object(FakeRoboticFacility, 'update_observation_status', return_value='COMPLETED') as uos_mock:
            FakeRoboticFacility().update_all_observation_statuses(target=self.t1)
            self.assertEqual(uos_mock.call_count, 2)


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

        airmass_data = airmass['(FakeRoboticFacility) Siding Spring'][1]
        expected_airmass = [
            1.2619096566629477, 1.2648181328558852, 1.2703522349950636, 1.2785703053923894,
            1.2895601364316183, 1.3034413026227516, 1.3203684217446099
        ]
        self.assertEqual(len(airmass_data), len(expected_airmass))
        for i, expected_airmass_value in enumerate(expected_airmass):
            self.assertAlmostEqual(airmass_data[i], expected_airmass_value, places=3)


class TestGetServiceClasses(TestCase):
    """
    Tests for the observation_facilities() AppConfig integration point as consumed by
    tom_observations.facility.get_service_classes().
    """

    def _fake_app_config(self, facilities: list) -> mock.Mock:
        """Return a mock AppConfig whose observation_facilities() returns the given list."""
        app_config = mock.Mock()
        app_config.name = 'fake_facility_app'
        app_config.observation_facilities.return_value = facilities
        return app_config

    @override_settings(TOM_FACILITY_CLASSES=['tom_observations.tests.utils.FakeRoboticFacility'])
    def test_app_contributed_facilities_merged_with_settings(self):
        fake_app_config = self._fake_app_config([{'class': 'tom_observations.tests.utils.FakeManualFacility'}])
        with mock.patch('tom_observations.facility.apps.get_app_configs', return_value=[fake_app_config]):
            service_classes = get_service_classes()
        self.assertEqual(service_classes,
                         {'FakeRoboticFacility': FakeRoboticFacility, 'FakeManualFacility': FakeManualFacility})

    @override_settings(TOM_FACILITY_CLASSES=['tom_observations.tests.utils.FakeRoboticFacility'])
    def test_facility_in_both_sources_is_deduplicated(self):
        fake_app_config = self._fake_app_config([{'class': 'tom_observations.tests.utils.FakeRoboticFacility'}])
        with mock.patch('tom_observations.facility.apps.get_app_configs', return_value=[fake_app_config]):
            service_classes = get_service_classes()
        self.assertEqual(service_classes, {'FakeRoboticFacility': FakeRoboticFacility})

    @override_settings(TOM_FACILITY_CLASSES=['tom_observations.tests.utils.FakeRoboticFacility'])
    def test_unimportable_app_facility_is_skipped_with_warning(self):
        fake_app_config = self._fake_app_config([{'class': 'no.such.module.NoSuchFacility'}])
        with mock.patch('tom_observations.facility.apps.get_app_configs', return_value=[fake_app_config]), \
                self.assertLogs('tom_observations.facility', level='WARNING'):
            service_classes = get_service_classes()
        self.assertEqual(service_classes, {'FakeRoboticFacility': FakeRoboticFacility})


class TestObservationFacilitiesNavbar(TestCase):
    """
    Tests for the "Facilities" navbar dropdown: the observation_facilities_list templatetag
    and its navbar_facilities_list.html partial.
    """

    def _patch_service_classes(self, *facility_classes):
        """Patch get_service_classes() to return exactly the given facility classes."""
        return mock.patch(
            'tom_observations.templatetags.observation_extras.get_service_classes',
            return_value={clazz.name: clazz for clazz in facility_classes})

    def test_facility_with_detail_url_name_is_listed(self):
        """Does the inclusiontag return a context with the correct Facility name and URL?
        """
        # 'home' is a URL name that always resolves, standing in for a facility detail page
        with mock.patch.object(FakeRoboticFacility, 'detail_url_name', 'home'), \
                self._patch_service_classes(FakeRoboticFacility):
            context = observation_facilities_list({})  # function under test
        self.assertEqual(context['observation_facilities'],
                         [{'name': 'FakeRoboticFacility', 'url': reverse('home')}])

    def test_facility_without_detail_url_name_gets_no_navbar_item_and_no_warning(self):
        """A facility that leaves detail_url_name as None is omitted from the navbar without logging a warning."""
        # registration-only facilities (e.g. tom_lt) have no detail page; their absence from
        # the navbar is deliberate, not a misconfiguration worth warning about
        with self._patch_service_classes(FakeRoboticFacility), \
                mock.patch('tom_observations.templatetags.observation_extras.logger') as mock_logger:
            context = observation_facilities_list({})  # function under test
        self.assertEqual(context['observation_facilities'], [])
        mock_logger.warning.assert_not_called()

    def test_facility_with_unresolvable_url_is_skipped_with_warning(self):
        """A facility whose detail_url_name does not reverse() is skipped with a warning, not an exception."""
        with mock.patch.object(FakeRoboticFacility, 'detail_url_name', 'no-such-url-name'), \
                self._patch_service_classes(FakeRoboticFacility), \
                self.assertLogs('tom_observations.templatetags.observation_extras', level='WARNING'):
            context = observation_facilities_list({})  # function under test
        self.assertEqual(context['observation_facilities'], [])

    def test_facility_class_without_the_attribute_is_skipped(self):
        """A facility class with no detail_url_name attribute at all is skipped rather than raising AttributeError."""
        # pins the getattr() in the tag: a facility class that doesn't inherit from
        # BaseObservationFacility must not 500 every page that renders the navbar
        class RogueFacility:
            name = 'RogueFacility'
            # no detail_url_name attribute

        with self._patch_service_classes(RogueFacility):
            context = observation_facilities_list({})  # function under test
        self.assertEqual(context['observation_facilities'], [])

    def test_no_facilities_yields_empty_context(self):
        """With no facilities registered, the tag still supplies the (empty) observation_facilities context key."""
        # the partial's {% if observation_facilities %} guard relies on the key always being present
        with self._patch_service_classes():
            context = observation_facilities_list({})
        self.assertEqual(context['observation_facilities'], [])

    def test_settings_declared_facility_can_appear_in_navbar(self):
        """A facility from TOM_FACILITY_CLASSES gets a navbar entry too, since the navbar is built
        from get_service_classes(), which merges settings- and app-declared facilities."""
        with mock.patch.object(FakeRoboticFacility, 'detail_url_name', 'home'), \
                self.settings(TOM_FACILITY_CLASSES=['tom_observations.tests.utils.FakeRoboticFacility']):
            context = observation_facilities_list({})  # function under test
        self.assertEqual(context['observation_facilities'],
                         [{'name': 'FakeRoboticFacility', 'url': reverse('home')}])

    def test_dropdown_rendered_with_facility_links(self):
        """The partial renders a Facilities dropdown with one link per facility, pointing at its URL."""
        html = render_to_string(
            template_name='tom_observations/partials/navbar_facilities_list.html',  # template under test
            context={'observation_facilities': [{'name': 'FakeRoboticFacility', 'url': '/fake/'}]})

        self.assertIn('Facilities', html)
        self.assertIn('href="/fake/"', html)
        self.assertIn('FakeRoboticFacility', html)

    def test_dropdown_hidden_when_no_facilities(self):
        """The partial renders no Facilities dropdown at all when there are no facilities to list."""
        html = render_to_string(
            template_name='tom_observations/partials/navbar_facilities_list.html',  # template under test
            context={'observation_facilities': []})
        self.assertNotIn('Facilities', html)

    def test_home_page_has_no_facilities_dropdown(self):
        """End to end: with no facility setting detail_url_name, the home page renders without the dropdown."""
        # nothing in tom_base's own test project sets detail_url_name (the built-in
        # LCO/Gemini/SOAR/Blanco facilities have no detail pages)
        response = self.client.get(reverse('home'))
        self.assertNotContains(response, '>Facilities<')
