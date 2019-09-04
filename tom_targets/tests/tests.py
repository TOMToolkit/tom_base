from django.test import TestCase, override_settings
from django.urls import reverse
from django.contrib.auth.models import User, Group
import pytz
import ephem
from astropy import units
from astropy.coordinates import Angle
import math
from unittest import mock
from datetime import datetime, timedelta

from .factories import SiderealTargetFactory, NonSiderealTargetFactory, TargetGroupingFactory
from tom_targets.models import Target, TargetExtra, TargetList
from tom_observations.utils import get_visibility, get_pyephem_instance_for_type
from tom_observations.tests.utils import FakeFacility
from tom_targets.import_targets import import_targets
from guardian.shortcuts import assign_perm


class TestTargetDetail(TestCase):
    def setUp(self):
        user = User.objects.create(username='testuser')
        self.client.force_login(user)
        self.st = SiderealTargetFactory.create()
        self.nst = NonSiderealTargetFactory.create()
        assign_perm('tom_targets.view_target', user, self.st)
        assign_perm('tom_targets.view_target', user, self.nst)

    def test_sidereal_target_detail(self):
        response = self.client.get(reverse('targets:detail', kwargs={'pk': self.st.id}))
        self.assertContains(response, self.st.id)

    def test_non_sidereal_target_detail(self):
        response = self.client.get(reverse('targets:detail', kwargs={'pk': self.nst.id}))
        self.assertContains(response, self.nst.id)

    @override_settings(EXTRA_FIELDS=[
        {'name': 'somefield', 'type': 'string'},
        {'name': 'hiddenfield', 'type': 'string', 'hidden': True},
    ])
    def test_extra_fields(self):
        self.st.save(extras={'somefield': 'somevalue', 'hiddenfield': 'hiddenvalue'})
        response = self.client.get(reverse('targets:detail', kwargs={'pk': self.st.id}))
        self.assertContains(response, 'somevalue')
        self.assertNotContains(response, 'hiddenvalue')


class TestTargetCreate(TestCase):
    def setUp(self):
        user = User.objects.create(username='testuser')
        self.client.force_login(user)
        self.group = Group.objects.create(name='agroup')
        user.groups.add(self.group)
        user.save()

    def test_target_create_form(self):
        response = self.client.get(reverse('targets:create'))
        self.assertContains(response, Target.SIDEREAL)
        self.assertContains(response, Target.NON_SIDEREAL)

    def test_create_target(self):
        target_data = {
            'name': 'test_target',
            'identifier': 'test_target_id',
            'type': Target.SIDEREAL,
            'ra': 123.456,
            'dec': -32.1,
            'groups': [self.group.id],
            'targetextra_set-TOTAL_FORMS': 1,
            'targetextra_set-INITIAL_FORMS': 0,
            'targetextra_set-MIN_NUM_FORMS': 0,
            'targetextra_set-MAX_NUM_FORMS': 1000,
            'targetextra_set-0-key': '',
            'targetextra_set-0-value': '',
        }
        response = self.client.post(reverse('targets:create'), data=target_data, follow=True)
        self.assertContains(response, target_data['name'])
        self.assertTrue(Target.objects.filter(name=target_data['name']).exists())

    def test_create_target_sexigesimal(self):
        """
        Using coordinates for Messier 1
        """
        target_data = {
            'name': 'test_target',
            'identifier': 'test_target_id',
            'type': Target.SIDEREAL,
            'ra': '05:34:31.94',
            'dec': '+22:00:52.2',
            'groups': [self.group.id],
            'targetextra_set-TOTAL_FORMS': 1,
            'targetextra_set-INITIAL_FORMS': 0,
            'targetextra_set-MIN_NUM_FORMS': 0,
            'targetextra_set-MAX_NUM_FORMS': 1000,
            'targetextra_set-0-key': '',
            'targetextra_set-0-value': '',
        }
        response = self.client.post(reverse('targets:create'), data=target_data, follow=True)
        self.assertContains(response, target_data['name'])
        target = Target.objects.get(name=target_data['name'])
        # Coordinates according to simbad
        self.assertAlmostEqual(target.ra, 83.63308, places=4)
        self.assertAlmostEqual(target.dec, 22.0145, places=4)

    def test_create_target_with_tags(self):
        """
        Using coordinates for Messier 1
        """
        target_data = {
            'name': 'test_target',
            'identifier': 'test_target_id',
            'type': Target.SIDEREAL,
            'ra': '05:34:31.94',
            'dec': '+22:00:52.2',
            'groups': [self.group.id],
            'targetextra_set-TOTAL_FORMS': 1,
            'targetextra_set-INITIAL_FORMS': 0,
            'targetextra_set-MIN_NUM_FORMS': 0,
            'targetextra_set-MAX_NUM_FORMS': 1000,
            'targetextra_set-0-key': 'category',
            'targetextra_set-0-value': 'type2',
        }
        response = self.client.post(reverse('targets:create'), data=target_data, follow=True)
        self.assertContains(response, target_data['name'])
        target = Target.objects.get(name=target_data['name'])
        self.assertTrue(target.targetextra_set.filter(key='category', value='type2').exists())

    @override_settings(EXTRA_FIELDS=[
        {'name': 'wins', 'type': 'number'},
        {'name': 'checked', 'type': 'boolean'},
        {'name': 'birthdate', 'type': 'datetime'},
        {'name': 'author', 'type': 'string'}

    ])
    def test_create_target_with_extra_fields(self):
        target_data = {
            'name': 'extra_field_target',
            'identifier': 'extra_field_identifier',
            'type': Target.SIDEREAL,
            'ra': 113.456,
            'dec': -22.1,
            'wins': 50.0,
            'checked': True,
            'birthdate': datetime(year=2019, month=2, day=14),
            'author': 'Dr. Suess',
            'groups': [self.group.id],
            'targetextra_set-TOTAL_FORMS': 1,
            'targetextra_set-INITIAL_FORMS': 0,
            'targetextra_set-MIN_NUM_FORMS': 0,
            'targetextra_set-MAX_NUM_FORMS': 1000,
            'targetextra_set-0-key': '',
            'targetextra_set-0-value': '',
        }
        response = self.client.post(reverse('targets:create'), data=target_data, follow=True)
        self.assertContains(response, target_data['name'])
        target = Target.objects.get(name=target_data['name'], identifier=target_data['identifier'])
        self.assertTrue(TargetExtra.objects.filter(target=target, key='wins', value='50.0').exists())
        self.assertEqual(
            TargetExtra.objects.get(target=target, key='wins').typed_value('number'),
            50.0
        )
        self.assertEqual(
            TargetExtra.objects.get(target=target, key='checked').typed_value('boolean'),
            True
        )
        self.assertEqual(
            TargetExtra.objects.get(target=target, key='birthdate').typed_value('datetime'),
            datetime(year=2019, month=2, day=14, tzinfo=pytz.UTC)
        )
        self.assertEqual(
            TargetExtra.objects.get(target=target, key='author').typed_value('string'),
            'Dr. Suess'
        )
        # Check extra_fields property converts values to the correct type
        self.assertIsInstance(target.extra_fields, dict)
        self.assertIsInstance(target.extra_fields['wins'], float)
        self.assertIsInstance(target.extra_fields['checked'], bool)
        self.assertIsInstance(target.extra_fields['birthdate'], datetime)
        self.assertIsInstance(target.extra_fields['author'], str)

    def test_target_save_programmatic_extras(self):
        target = SiderealTargetFactory.create()
        target.save(extras={'foo': 5})
        self.assertTrue(TargetExtra.objects.filter(target=target, key='foo', value='5').exists())


class TestTargetImport(TestCase):
    def setUp(self):
        user = User.objects.create(username='testuser')
        self.client.force_login(user)

    def test_import_csv(self):
        csv = [
            'identifier,name,type,ra,dec',
            'm13,Hercules Globular Cluster,SIDEREAL,250.421,36.459',
            'm27,Dumbbell Nebula,SIDEREAL,299.901,22.721'
        ]
        result = import_targets(csv)
        self.assertEqual(len(result['targets']), 2)

    @override_settings(EXTRA_FIELDS=[{'name': 'redshift', 'type': 'number'}])
    def test_import_with_extra(self):
        csv = [
            'identifier,name,type,ra,dec,redshift',
            'm13,Hercules Globular Cluster,SIDEREAL,250.421,36.459,5',
            'm27,Dumbbell Nebula,SIDEREAL,299.901,22.721,5'
        ]
        result = import_targets(csv)
        self.assertEqual(len(result['targets']), 2)
        for target in result['targets']:
            self.assertTrue(TargetExtra.objects.filter(target=target, key='redshift', value='5').exists())


class TestTargetSearch(TestCase):
    def setUp(self):
        self.st = SiderealTargetFactory.create(identifier='1337target', name='M42', name2='Messier 42')
        user = User.objects.create(username='testuser')
        self.client.force_login(user)
        assign_perm('tom_targets.view_target', user, self.st)

    def test_search_name_no_results(self):
        response = self.client.get(reverse('targets:list') + '?name=noresults')
        self.assertNotContains(response, '1337target')

    def test_search_name(self):
        response = self.client.get(reverse('targets:list') + '?name=m42')
        self.assertContains(response, '1337target')

        response = self.client.get(reverse('targets:list') + '?name=Messier 42')
        self.assertContains(response, '1337target')

    @override_settings(EXTRA_FIELDS=[{'name': 'color', 'type': 'string'}])
    def test_search_extra_fields(self):
        TargetExtra.objects.create(target=self.st, key='color', value='red')

        response = self.client.get(reverse('targets:list') + '?color=red')
        self.assertContains(response, '1337target')

        response = self.client.get(reverse('targets:list') + '?color=blue')
        self.assertNotContains(response, '1337target')

    @override_settings(EXTRA_FIELDS=[{'name': 'birthday', 'type': 'datetime'}])
    def test_search_extra_datetime(self):
        TargetExtra.objects.create(target=self.st, key='birthday', value='2019-02-14')

        response = self.client.get(reverse('targets:list') + '?birthday_after=2019-02-13&birthday_before=2019-02-15')
        self.assertContains(response, '1337target')

    @override_settings(EXTRA_FIELDS=[{'name': 'checked', 'type': 'boolean'}])
    def test_search_extra_boolean(self):
        TargetExtra.objects.create(target=self.st, key='checked', value=False)

        response = self.client.get(reverse('targets:list') + '?checked=3')
        self.assertContains(response, '1337target')


class TestTargetVisibility(TestCase):
    def setUp(self):
        self.mars = ephem.Mars()
        self.time = datetime(2018, 10, 10, 7, 0, 0)
        self.mars.compute(self.time)
        ra = Angle(str(self.mars.ra), unit=units.hourangle)
        dec = Angle(str(self.mars.dec) + 'd', unit=units.deg)
        self.st = Target(ra=ra.deg, dec=dec.deg, type=Target.SIDEREAL)
        self.nst = Target(
            inclination=89.4245,
            lng_asc_node=282.4515,
            arg_of_perihelion=130.5641,
            semimajor_axis=183.6816,
            mean_daily_motion=0.0003959,
            eccentricity=0.995026,
            mean_anomaly=0.1825,
            ephemeris_epoch=2451000.5,
            type=Target.NON_SIDEREAL
        )

    def test_get_pyephem_instance_for_sidereal(self):
        target_ephem = get_pyephem_instance_for_type(self.st)
        target_ephem.compute(self.time)
        self.assertIsInstance(target_ephem, type(ephem.FixedBody()))
        self.assertLess(math.fabs(target_ephem.ra-self.mars.ra), 0.5)
        self.assertLess(math.fabs(target_ephem.dec-self.mars.dec), 0.5)

    def test_get_pyephem_instance_for_non_sidereal(self):
        hb = ephem.readdb(
            'C/1995 O1 (Hale-Bopp),e,89.4245,282.4515,130.5641,183.6816,'
            '0.0003959,0.995026,0.1825,07/06.0/1998,2000,g -2.0,4.0'
        )
        target_ephem = get_pyephem_instance_for_type(self.nst)
        location = ephem.city('Los Angeles')
        location.date = ephem.date(datetime.now())
        hb.compute(location)
        target_ephem.compute(location)
        self.assertLess(math.fabs(target_ephem.ra-hb.ra), 0.5)
        self.assertLess(math.fabs(target_ephem.dec-hb.dec), 0.5)

    def test_get_pyephem_instance_invalid_type(self):
        self.st.type = 'Fake Type'
        with self.assertRaises(Exception):
            get_pyephem_instance_for_type(self.st)

    @mock.patch('tom_observations.utils.facility.get_service_classes')
    @mock.patch('tom_observations.utils.get_rise_set')
    @mock.patch('tom_observations.utils.observer_for_site')
    def test_get_visibility_sidereal(self, mock_observer_for_site, mock_get_rise_set, mock_facility):
        mock_facility.return_value = {'Fake Facility': FakeFacility}
        mock_get_rise_set.return_value = []
        mock_observer_for_site.return_value = ephem.city('Los Angeles')

        start = self.time
        end = start + timedelta(minutes=60)
        expected_airmass = [
            3.6074370614681017, 3.997263815883785, 4.498087520663738, 5.162731916462906,
            6.083298253498044, 7.4363610371608475, 9.607152214891583
        ]

        airmass_data = get_visibility(self.st, start, end, 10, 10)['(Fake Facility) Los Angeles'][1]
        self.assertEqual(len(airmass_data), len(expected_airmass))
        for i in range(0, len(expected_airmass)):
            self.assertEqual(airmass_data[i], expected_airmass[i])

    @mock.patch('tom_observations.utils.facility.get_service_classes')
    @mock.patch('tom_observations.utils.get_rise_set')
    @mock.patch('tom_observations.utils.observer_for_site')
    def test_get_visibility_non_sidereal(self, mock_observer_for_site, mock_get_rise_set, mock_facility):
        mock_facility.return_value = {'Fake Facility': FakeFacility}
        mock_get_rise_set.return_value = []
        mock_observer_for_site.return_value = ephem.city('Los Angeles')

        start = datetime(1997, 4, 1, 0, 0, 0)
        end = start + timedelta(minutes=60)
        expected_airmass = [
            1.225532769770131, 1.2536644126634366, 1.2843810879053679, 1.3179084796712417,
            1.3545030240774714, 1.3944575296459614, 1.4381124914948578
        ]

        airmass_data = get_visibility(self.nst, start, end, 10, 10)['(Fake Facility) Los Angeles'][1]
        self.assertEqual(len(airmass_data), len(expected_airmass))
        for i in range(0, len(expected_airmass)):
            self.assertLess(math.fabs(airmass_data[i] - expected_airmass[i]), 0.05)


class TestTargetGrouping(TestCase):
    def setUp(self):
        user = User.objects.create(username='testuser')
        self.client.force_login(user)

    def test_view_groupings(self):
        # create a group, check it is added to DB
        group = TargetList(name="test_group")
        group.save()
        self.assertTrue(TargetList.objects.filter(name="test_group").exists())

        # give this user the permission to view it
        user = User.objects.get(username='testuser')
        assign_perm('tom_targets.view_targetlist', user, group)

        response = self.client.get(reverse('targets:targetgrouping'), follow=True)
        self.assertContains(response, group.name)

    def test_create_group(self):
        group_data = {
            'name': 'test_group'
        }
        response = self.client.post(reverse('targets:create-group'), data=group_data)

        self.assertRedirects(response, reverse('targets:targetgrouping'), status_code=302)
        self.assertTrue(TargetList.objects.filter(name=group_data['name']).exists())

    def test_delete_group(self):
        # create a group, check it is added to DB
        group = TargetList(name="test_group")
        group.save()
        self.assertTrue(TargetList.objects.filter(name="test_group").exists())

        # give user permission to delete
        user = User.objects.get(username='testuser')
        assign_perm('tom_targets.delete_targetlist', user, group)

        response = self.client.post(reverse('targets:delete-group', args=(group.pk,)), follow=True)
        self.assertRedirects(response, reverse('targets:targetgrouping'), status_code=302)
        self.assertFalse(TargetList.objects.filter(name='test_group').exists())


class TestTargetAddRemoveGrouping(TestCase):
    def setUp(self):
        user = User.objects.create(username='testuser')
        self.client.force_login(user)
        # create targets
        self.fake_targets = []
        for i in range(3):
            ft = SiderealTargetFactory.create()
            self.fake_targets.append(ft)
            assign_perm('tom_targets.view_target', user, ft)
        # create grouping
        self.fake_grouping = TargetGroupingFactory.create()
        assign_perm('tom_targets.view_targetlist', user, self.fake_grouping)
        # add target[0] to grouping
        self.fake_grouping.targets.add(self.fake_targets[0])

    # Add target[0] and [1] to grouping; [0] already exists and [1] new
    def test_add_selected_to_grouping(self):
        data = {
            'grouping': self.fake_grouping.id,
            'add': True,
            'isSelectAll': 'False',
            'selected-target': [self.fake_targets[0].id, self.fake_targets[1].id],
            'query_string': '',
        }
        response = self.client.post(reverse('targets:add-remove-grouping'), data=data)

        self.assertEqual(self.fake_grouping.targets.count(), 2)
        self.assertTrue(self.fake_targets[0] in self.fake_grouping.targets.all())
        self.assertTrue(self.fake_targets[1] in self.fake_grouping.targets.all())

    def test_add_to_invalid_grouping(self):
        data = {
            'grouping': -1,
            'add': True,
            'isSelectAll': 'False',
            'selected-target': self.fake_targets[1].id,
            'query_string': '',
        }
        self.client.post(reverse('targets:add-remove-grouping'), data=data)
        self.assertEqual(self.fake_grouping.targets.count(), 1)
        self.assertTrue(self.fake_targets[0] in self.fake_grouping.targets.all())

    # Remove target[0] and [1] from grouping;
    def test_remove_selected_from_grouping(self):
        data = {
            'grouping': self.fake_grouping.id,
            'remove': True,
            'isSelectAll': 'False',
            'selected-target': [self.fake_targets[0].id, self.fake_targets[1].id],
            'query_string': '',
        }
        self.client.post(reverse('targets:add-remove-grouping'), data=data)
        self.assertEqual(self.fake_grouping.targets.count(), 0)

    def test_empty_data(self):
        self.client.post(reverse('targets:add-remove-grouping'), data={'query_string': ''})
        self.assertEqual(self.fake_grouping.targets.count(), 1)

    def test_permission_denied(self):
        new_user = User.objects.create(username='newuser')
        self.client.force_login(new_user)
        data = {
            'grouping': self.fake_grouping.id,
            'add': True,
            'isSelectAll': 'False',
            'selected-target': [self.fake_targets[0].id, self.fake_targets[1].id],
            'query_string': '',
        }
        self.client.post(reverse('targets:add-remove-grouping'), data=data)
        self.assertEqual(self.fake_grouping.targets.count(), 1)

    def test_add_all_to_grouping_filtered_by_sidereal(self):
        data = {
            'grouping': self.fake_grouping.id,
            'add': True,
            'isSelectAll': 'True',
            'selected-target': [],
            'query_string': 'type=SIDEREAL&identifier=&name=&key=&value=&targetlist__name=',
        }
        response = self.client.post(reverse('targets:add-remove-grouping'), data=data)
        self.assertEqual(self.fake_grouping.targets.count(), 3)

    def test_remove_all_from_grouping_filtered_by_sidereal(self):
        data = {
            'grouping': self.fake_grouping.id,
            'remove': True,
            'isSelectAll': 'True',
            'selected-target': [],
            'query_string': 'type=SIDEREAL&identifier=&name=&key=&value=&targetlist__name=',
        }
        response = self.client.post(reverse('targets:add-remove-grouping'), data=data)
        self.assertEqual(self.fake_grouping.targets.count(), 0)

    def test_remove_all_from_grouping_filtered_by_grouping(self):
        data = {
            'grouping': self.fake_grouping.id,
            'remove': True,
            'isSelectAll': 'True',
            'selected-target': [],
            'query_string': 'type=&identifier=&name=&key=&value=&targetlist__name=' + str(self.fake_grouping.id),
        }
        response = self.client.post(reverse('targets:add-remove-grouping'), data=data)
        self.assertEqual(self.fake_grouping.targets.count(), 0)

    def test_add_remove_with_random_query_string(self):
        data = {
            'grouping': self.fake_grouping.id,
            'remove': True,
            'isSelectAll': 'True',
            'selected-target': [],
            'query_string': 'asdfghjk@!#$%6',
        }
        self.client.post(reverse('targets:add-remove-grouping'), data=data)
        self.assertEqual(self.fake_grouping.targets.count(), 0)

    def test_add_remove_from_grouping_empty_query_string(self):
        data = {
            'grouping': self.fake_grouping.id,
            'remove': True,
            'isSelectAll': 'True',
            'selected-target': [],
        }
        self.client.post(reverse('targets:add-remove-grouping'), data=data)
        self.assertEqual(self.fake_grouping.targets.count(), 0)

    def test_persist_filter(self):
        data = {'query_string': "type=SIDEREAL&identifier=A&name=B&key=C&value=123&targetlist__name=1"}
        expected_query_dict = {
            'type': 'SIDEREAL',
            'identifier': 'A',
            'name': 'B',
            'key': 'C',
            'value': '123',
            'targetlist__name': '1'}
        response = self.client.post(reverse('targets:add-remove-grouping'), data=data, follow=True)
        response_query_dict = response.context['filter'].data.dict()
        self.assertEqual(response_query_dict, expected_query_dict)

    def test_persist_filter_empty(self):
        data = {}
        expected_query_dict = {}
        response = self.client.post(reverse('targets:add-remove-grouping'), data=data, follow=True)
        response_query_dict = response.context['filter'].data
        self.assertEqual(response_query_dict, expected_query_dict)
