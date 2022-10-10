import pytz
from datetime import datetime

from django.contrib.auth.models import User, Group
from django.contrib.messages import get_messages
from django.contrib.messages.constants import SUCCESS, WARNING
from django.test import TestCase, override_settings
from django.urls import reverse

from .factories import SiderealTargetFactory, NonSiderealTargetFactory, TargetGroupingFactory, TargetNameFactory
from tom_targets.models import Target, TargetExtra, TargetList, TargetName
from tom_targets.utils import import_targets
from guardian.shortcuts import assign_perm


class TestTargetListUserPermissions(TestCase):
    def setUp(self):
        self.user = User.objects.create(username='testuser')
        self.user2 = User.objects.create(username='unauthorized')
        self.st1 = SiderealTargetFactory.create()
        self.st2 = SiderealTargetFactory.create()

        assign_perm('tom_targets.view_target', self.user, self.st1)
        assign_perm('tom_targets.view_target', self.user, self.st2)
        assign_perm('tom_targets.view_target', self.user2, self.st2)

    def test_list_targets(self):
        self.client.force_login(self.user)
        response = self.client.get(reverse('targets:list'))
        self.assertContains(response, self.st1.name)
        self.assertContains(response, self.st2.name)

    def test_list_targets_limited_permissions(self):
        self.client.force_login(self.user2)
        response = self.client.get(reverse('targets:list'))
        self.assertContains(response, self.st2.name)
        self.assertNotContains(response, self.st1.name)


class TestTargetListGroupPermissions(TestCase):
    def setUp(self):
        self.user = User.objects.create(username='testuser')
        self.user2 = User.objects.create(username='unauthorized')
        self.st1 = SiderealTargetFactory.create()
        self.st2 = SiderealTargetFactory.create()
        self.group1 = Group.objects.create(name='group1')
        self.group2 = Group.objects.create(name='group2')
        self.group1.user_set.add(self.user)
        self.group2.user_set.add(self.user)
        self.group2.user_set.add(self.user2)

        assign_perm('tom_targets.view_target', self.group1, self.st1)
        assign_perm('tom_targets.view_target', self.group2, self.st2)

    def test_list_targets(self):
        self.client.force_login(self.user)
        response = self.client.get(reverse('targets:list'))
        self.assertContains(response, self.st1.name)
        self.assertContains(response, self.st2.name)

    def test_list_targets_limited_permissions(self):
        self.client.force_login(self.user2)
        response = self.client.get(reverse('targets:list'))
        self.assertContains(response, self.st2.name)
        self.assertNotContains(response, self.st1.name)


# Because the target detail page has a templatetag that tries to get the facility status, these tests fail without
# network. While the preferred solution would be to create a mock facility class, in order to avoid any potential
# circular imports, we're simply disabling the facility classes for these tests. This can be revisited if need be at a
# future time, but currently the target tests don't do anything with ObservationRecords anyway.
@override_settings(TOM_FACILITY_CLASSES=[])
class TestTargetDetail(TestCase):
    def setUp(self):
        user = User.objects.create(username='testuser')
        self.client.force_login(user)
        self.st = SiderealTargetFactory.create(ra=123.456, dec=-32.1)
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

    def test_target_bad_permissions(self):
        other_user = User.objects.create(username='otheruser')
        self.client.force_login(other_user)
        response = self.client.get(reverse('targets:detail', kwargs={'pk': self.st.id}), follow=True)
        self.assertRedirects(response, '{}?next=/targets/{}/'.format(reverse('login'), self.st.id))
        self.assertContains(response, 'You do not have permission to access this page')


class TestTargetNameSearch(TestCase):
    def setUp(self):
        self.user = User.objects.create(username='testuser')
        self.user2 = User.objects.create(username='testuser2')

        self.st1 = SiderealTargetFactory.create(name='testtarget1')
        self.st2 = SiderealTargetFactory.create(name='testtarget2')
        self.st3 = SiderealTargetFactory.create(name='testtarget3')

        assign_perm('tom_targets.view_target', self.user, self.st1)
        assign_perm('tom_targets.view_target', self.user2, self.st1)
        assign_perm('tom_targets.view_target', self.user, self.st2)
        assign_perm('tom_targets.view_target', self.user, self.st3)

    def test_search_one_result(self):
        """Test that a search with one result returns the target detail page."""
        self.client.force_login(self.user)
        response = self.client.get(reverse('targets:name-search', kwargs={'name': self.st1.name}), follow=True)
        self.assertRedirects(response, reverse('targets:detail', kwargs={'pk': self.st1.id}))
        self.assertContains(response, self.st1.name)

    def test_search_no_results(self):
        """Test that a search with no results returns the target list page."""
        self.client.force_login(self.user)
        response = self.client.get(reverse('targets:name-search', kwargs={'name': 'fakename'}), follow=True)
        self.assertRedirects(response, reverse('targets:list') + '?name=fakename')
        self.assertNotContains(response, self.st1.name)
        self.assertNotContains(response, self.st2.name)

    def test_search_multiple_results(self):
        """Test that a search with multiple results returns the target list page."""
        self.client.force_login(self.user)
        response = self.client.get(reverse('targets:name-search', kwargs={'name': 'testtarget'}), follow=True)
        self.assertRedirects(response, reverse('targets:list') + '?name=testtarget')
        self.assertContains(response, self.st1.name)
        self.assertContains(response, self.st3.name)

    def test_search_one_result_unauthorized(self):
        """Test that a search with one result that the user is not allowed to view returns an empty target list page."""
        self.client.force_login(self.user2)
        response = self.client.get(reverse('targets:name-search', kwargs={'name': 'testtarget3'}), follow=True)
        self.assertRedirects(response, reverse('targets:list') + '?name=testtarget3')
        self.assertContains(response, 'No targets match those filters.')

    def test_search_multiple_results_unauthorized(self):
        """Test that a search with multiple results returns the target list page, but without the targets that
           the user is not allowed to view."""
        assign_perm('tom_targets.view_target', self.user2, self.st2)
        self.client.force_login(self.user2)
        response = self.client.get(reverse('targets:name-search', kwargs={'name': 'testtarget'}), follow=True)
        self.assertRedirects(response, reverse('targets:list') + '?name=testtarget')
        self.assertContains(response, self.st1.name)
        self.assertNotContains(response, self.st3.name)

    def test_search_one_result_authorized(self):
        """Test that a search with only one result that the user is allowed to view returns the target detail page."""
        self.client.force_login(self.user2)
        response = self.client.get(reverse('targets:name-search', kwargs={'name': 'testtarget'}), follow=True)
        self.assertRedirects(response, reverse('targets:detail', kwargs={'pk': self.st1.id}))
        self.assertContains(response, self.st1.name)


@override_settings(TOM_FACILITY_CLASSES=[])
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
            'name': 'test_target_name',
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
            'aliases-TOTAL_FORMS': 1,
            'aliases-INITIAL_FORMS': 0,
            'aliases-MIN_NUM_FORMS': 0,
            'aliases-MAX_NUM_FORMS': 1000,
        }
        response = self.client.post(reverse('targets:create'), data=target_data, follow=True)
        self.assertContains(response, target_data['name'])
        self.assertTrue(Target.objects.filter(name=target_data['name']).exists())

    def test_create_target_sexigesimal(self):
        """
        Using coordinates for Messier 1
        """
        target_data = {
            'name': 'test_target_name',
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
            'aliases-TOTAL_FORMS': 1,
            'aliases-INITIAL_FORMS': 0,
            'aliases-MIN_NUM_FORMS': 0,
            'aliases-MAX_NUM_FORMS': 1000,
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
            'aliases-TOTAL_FORMS': 1,
            'aliases-INITIAL_FORMS': 0,
            'aliases-MIN_NUM_FORMS': 0,
            'aliases-MAX_NUM_FORMS': 1000,
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
            'aliases-TOTAL_FORMS': 1,
            'aliases-INITIAL_FORMS': 0,
            'aliases-MIN_NUM_FORMS': 0,
            'aliases-MAX_NUM_FORMS': 1000,
        }
        response = self.client.post(reverse('targets:create'), data=target_data, follow=True)
        self.assertContains(response, target_data['name'])
        target = Target.objects.get(name=target_data['name'])
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

    def test_none_extra(self):
        target = SiderealTargetFactory.create()
        target.save(extras={'foo': None})
        self.assertTrue(TargetExtra.objects.filter(target=target, key='foo').exists())

    def test_datetime_warning(self):
        '''Tests for an int that might come in and get mistakenly parsed for a datetime
        If the value can be successfully cast as a float it is not useful to us as a datetime
        Casting a datetime from an int will indicate that year on an arbitrary day. '''
        target = SiderealTargetFactory.create()
        target.save(extras={'foo': '1984'})
        te = target.targetextra_set.get(key='foo')
        self.assertEquals(te.typed_value('number'), 1984.0)
        self.assertIsNone(te.typed_value('datetime'))

    def test_non_sidereal_required_fields(self):
        base_data = {
            'name': 'nonsidereal_target',
            'identifier': 'nonsidereal_identifier',
            'type': Target.NON_SIDEREAL,
            'epoch_of_elements': 100,
            'lng_asc_node': 100,
            'arg_of_perihelion': 100,
            'eccentricity': 100,
            'mean_anomaly': 100,
            'inclination': 100,
            'semimajor_axis': 100,
            'targetextra_set-TOTAL_FORMS': 1,
            'targetextra_set-INITIAL_FORMS': 0,
            'targetextra_set-MIN_NUM_FORMS': 0,
            'targetextra_set-MAX_NUM_FORMS': 1000,
            'targetextra_set-0-key': '',
            'targetextra_set-0-value': '',
            'aliases-TOTAL_FORMS': 1,
            'aliases-INITIAL_FORMS': 0,
            'aliases-MIN_NUM_FORMS': 0,
            'aliases-MAX_NUM_FORMS': 1000,
        }
        create_url = reverse('targets:create') + '?type=NON_SIDEREAL'

        # Make data for a major planet scheme: missing 'mean_daily_motion'
        maj_planet_data = dict(**base_data, scheme='JPL_MAJOR_PLANET')
        response = self.client.post(create_url, data=maj_planet_data, follow=True)
        errors = response.context['form'].errors
        self.assertEqual(set(errors.keys()), {'__all__'})
        messages = errors['__all__']
        self.assertEqual(len(messages), 1)
        self.assertTrue(messages[0].startswith("Scheme 'JPL Major Planet' requires fields"))
        self.assertIn('Daily Motion', messages[0])

        # Use the same data for minor planet: should be no errors
        min_planet_data = dict(**base_data, scheme='MPC_MINOR_PLANET')
        response = self.client.post(create_url, data=min_planet_data, follow=True)
        errors = response.context['form'].errors
        self.assertEqual(errors, {})

    def test_create_form_failure(self):
        """
        If a failure occurs when creating a non-sidereal target, make sure the
        user is shown the non-sidereal form (not the sidereal one)
        """
        target_data = {
            'name': 'test_target',
            'type': Target.NON_SIDEREAL,
            'scheme': 'MPC_MINOR_PLANET',
            # Miss out a load of required fields...
            'targetextra_set-TOTAL_FORMS': 1,
            'targetextra_set-INITIAL_FORMS': 0,
            'targetextra_set-MIN_NUM_FORMS': 0,
            'targetextra_set-MAX_NUM_FORMS': 1000,
            'targetextra_set-0-key': '',
            'targetextra_set-0-value': '',
            'aliases-TOTAL_FORMS': 1,
            'aliases-INITIAL_FORMS': 0,
            'aliases-MIN_NUM_FORMS': 0,
            'aliases-MAX_NUM_FORMS': 1000,
        }
        response = self.client.post(reverse('targets:create'), data=target_data)
        self.assertEqual(response.context['form'].initial['type'], Target.NON_SIDEREAL)

    def test_create_targets_with_multiple_names(self):
        target_data = {
            'name': 'multiple_names_target',
            'type': Target.SIDEREAL,
            'ra': 113.456,
            'dec': -22.1,
            'groups': [self.group.id],
            'targetextra_set-TOTAL_FORMS': 1,
            'targetextra_set-INITIAL_FORMS': 0,
            'targetextra_set-MIN_NUM_FORMS': 0,
            'targetextra_set-MAX_NUM_FORMS': 1000,
            'targetextra_set-0-key': '',
            'targetextra_set-0-value': '',
            'aliases-TOTAL_FORMS': 2,
            'aliases-INITIAL_FORMS': 0,
            'aliases-MIN_NUM_FORMS': 0,
            'aliases-MAX_NUM_FORMS': 1000,
        }
        names = ['John', 'Doe']
        for i, name in enumerate(names):
            target_data[f'aliases-{i}-name'] = name
        response = self.client.post(reverse('targets:create'), data=target_data, follow=True)
        self.assertContains(response, target_data['name'])

        target = Target.objects.get(name=target_data['name'])
        for target_name in names:
            self.assertTrue(TargetName.objects.filter(target=target, name=target_name).exists())

    def test_create_targets_with_conflicting_names(self):
        target_data = {
            'name': 'multiple_names_target',
            'type': Target.SIDEREAL,
            'ra': 113.456,
            'dec': -22.1,
            'groups': [self.group.id],
            'targetextra_set-TOTAL_FORMS': 1,
            'targetextra_set-INITIAL_FORMS': 0,
            'targetextra_set-MIN_NUM_FORMS': 0,
            'targetextra_set-MAX_NUM_FORMS': 1000,
            'targetextra_set-0-key': '',
            'targetextra_set-0-value': '',
            'aliases-TOTAL_FORMS': 2,
            'aliases-INITIAL_FORMS': 0,
            'aliases-MIN_NUM_FORMS': 0,
            'aliases-MAX_NUM_FORMS': 1000,
        }
        names = ['John', 'Doe']
        for i, name in enumerate(names):
            target_data[f'aliases-{i}-name'] = name
        self.client.post(reverse('targets:create'), data=target_data, follow=True)
        second_response = self.client.post(reverse('targets:create'), data=target_data, follow=True)
        self.assertContains(second_response, 'Target with this Name already exists')

    def test_create_targets_with_conflicting_aliases(self):
        target_data = {
            'name': 'multiple_names_target',
            'type': Target.SIDEREAL,
            'ra': 113.456,
            'dec': -22.1,
            'groups': [self.group.id],
            'targetextra_set-TOTAL_FORMS': 1,
            'targetextra_set-INITIAL_FORMS': 0,
            'targetextra_set-MIN_NUM_FORMS': 0,
            'targetextra_set-MAX_NUM_FORMS': 1000,
            'targetextra_set-0-key': '',
            'targetextra_set-0-value': '',
            'aliases-TOTAL_FORMS': 2,
            'aliases-INITIAL_FORMS': 0,
            'aliases-MIN_NUM_FORMS': 0,
            'aliases-MAX_NUM_FORMS': 1000,
        }
        names = ['John', 'Doe']
        for i, name in enumerate(names):
            target_data[f'aliases-{i}-name'] = name
        self.client.post(reverse('targets:create'), data=target_data, follow=True)
        target_data['name'] = 'multiple_names_target2'
        second_response = self.client.post(reverse('targets:create'), data=target_data, follow=True)
        self.assertContains(second_response, 'Target name with this Alias already exists.')


class TestTargetUpdate(TestCase):
    def setUp(self):
        self.form_data = {
            'name': 'testtarget',
            'type': Target.SIDEREAL,
            'ra': 113.456,
            'dec': -22.1
        }
        user = User.objects.create(username='testuser')
        self.target = Target.objects.create(**self.form_data)
        assign_perm('tom_targets.change_target', user, self.target)
        self.client.force_login(user)

    def test_valid_update(self):
        self.form_data.update({
            'targetextra_set-TOTAL_FORMS': 1,
            'targetextra_set-INITIAL_FORMS': 0,
            'targetextra_set-MIN_NUM_FORMS': 0,
            'targetextra_set-MAX_NUM_FORMS': 1000,
            'targetextra_set-0-key': 'redshift',
            'targetextra_set-0-value': '3',
            'aliases-TOTAL_FORMS': 1,
            'aliases-INITIAL_FORMS': 0,
            'aliases-MIN_NUM_FORMS': 0,
            'aliases-MAX_NUM_FORMS': 1000,
            'aliases-0-name': 'testtargetname2'
        })
        self.client.post(reverse('targets:update', kwargs={'pk': self.target.id}), data=self.form_data)
        self.target.refresh_from_db()
        self.assertTrue(self.target.targetextra_set.filter(key='redshift').exists())
        self.assertTrue(self.target.aliases.filter(name='testtargetname2').exists())

    def test_invalid_alias_update(self):
        self.form_data.update({
            'targetextra_set-TOTAL_FORMS': 1,
            'targetextra_set-INITIAL_FORMS': 0,
            'targetextra_set-MIN_NUM_FORMS': 0,
            'targetextra_set-MAX_NUM_FORMS': 1000,
            'aliases-TOTAL_FORMS': 1,
            'aliases-INITIAL_FORMS': 0,
            'aliases-MIN_NUM_FORMS': 0,
            'aliases-MAX_NUM_FORMS': 1000,
            'aliases-0-name': 'testtarget'
        })
        # Try to add alias that is the same as target name (not allowed)
        response = self.client.post(reverse('targets:update', kwargs={'pk': self.target.id}), data=self.form_data)
        self.assertContains(response, 'Alias testtarget has a conflict with the primary name of the target')
        # Show Alias was not saved
        self.target.refresh_from_db()
        self.assertFalse(self.target.aliases.filter(name='testtarget').exists())

    def test_invalid_name_update(self):
        self.form_data.update({
            'targetextra_set-TOTAL_FORMS': 0,
            'targetextra_set-INITIAL_FORMS': 0,
            'targetextra_set-MIN_NUM_FORMS': 0,
            'targetextra_set-MAX_NUM_FORMS': 1000,
            'aliases-TOTAL_FORMS': 1,
            'aliases-INITIAL_FORMS': 0,
            'aliases-MIN_NUM_FORMS': 0,
            'aliases-MAX_NUM_FORMS': 1000,
            'aliases-0-name': 'testtargetname2'
        })
        # Set alias
        self.client.post(reverse('targets:update', kwargs={'pk': self.target.id}), data=self.form_data)
        self.target.refresh_from_db()
        self.assertTrue(self.target.aliases.filter(name='testtargetname2').exists())
        # Change name to same as alias (Not allowed)
        self.form_data.update({
            'name': 'testtargetname2',
        })
        response = self.client.post(reverse('targets:update', kwargs={'pk': self.target.id}), data=self.form_data)
        self.assertContains(response, 'Target name and target aliases must be different')
        # Show name change was unsuccessful
        self.target.refresh_from_db()
        self.assertTrue(self.target.name, 'testtarget')


class TestTargetImport(TestCase):
    def setUp(self):
        user = User.objects.create(username='testuser')
        self.client.force_login(user)

    def test_import_csv(self):
        csv = [
            'name,type,ra,dec',
            'm13,SIDEREAL,250.421,36.459',
            'm27,SIDEREAL,299.901,22.721'
        ]
        result = import_targets(csv)
        self.assertEqual(len(result['targets']), 2)

    @override_settings(EXTRA_FIELDS=[{'name': 'redshift', 'type': 'number'}])
    def test_import_with_extra(self):
        csv = [
            'name,type,ra,dec,redshift',
            'm13,SIDEREAL,250.421,36.459,5',
            'm27,SIDEREAL,299.901,22.721,5'
        ]
        result = import_targets(csv)
        self.assertEqual(len(result['targets']), 2)
        for target in result['targets']:
            self.assertTrue(TargetExtra.objects.filter(target=target, key='redshift', value='5').exists())

    def test_import_csv_with_multiple_names(self):
        csv = [
            'name,type,ra,dec,name1,name2',
            'm13,SIDEREAL,250.421,36.459,Tom,Joe',
            'm27,SIDEREAL,299.901,22.721,John,Doe'
        ]
        result = import_targets(csv)
        self.assertEqual(len(result['targets']), 2)
        aliases = {'m13': 'Tom,Joe', 'm27': 'John,Doe'}
        for target_name in aliases:
            target = Target.objects.get(name=target_name)
            for alias in aliases[target_name].split(','):
                self.assertTrue(TargetName.objects.filter(target=target, name=alias).exists())


class TestTargetExport(TestCase):
    """
    The use of a list to handle the map returned by StreamingHttpResponse.streaming_content is taken directly from
    the Django httpwrappers tests, as seen here:
    https://github.com/django/django/blob/00ff7a44dee91be59a64559cadeeba0f7386fd6f/tests/httpwrappers/tests.py#L569

    Tests are included for targets with and without aliases due to the previous presence of a bug relating to aliases
    and target export: https://github.com/TOMToolkit/tom_base/issues/265
    """
    def setUp(self):
        self.st = SiderealTargetFactory.create(name='M42', ra=83.8221, dec=-5.3911)
        self.st2 = SiderealTargetFactory.create(name='M52', ra=351.2, dec=61.593)

        self.user = User.objects.create(username='testuser')
        self.client.force_login(self.user)
        assign_perm('tom_targets.view_target',  self.user, self.st)
        assign_perm('tom_targets.view_target',  self.user, self.st2)

    def test_export_all_targets_no_aliases(self):
        response = self.client.get(reverse('targets:export'))
        content = ''.join(line.decode('utf-8') for line in list(response.streaming_content))
        self.assertIn('M42', content)
        self.assertIn('M52', content)

    def test_export_filtered_targets_no_aliases(self):
        response = self.client.get(reverse('targets:export') + '?name=M42')
        content = ''.join(line.decode('utf-8') for line in list(response.streaming_content))
        self.assertIn('M42', content)
        self.assertNotIn('M52', content)

    def test_export_all_targets_with_aliases(self):
        TargetNameFactory.create(name='Messier 42', target=self.st)
        response = self.client.get(reverse('targets:export'))
        content = ''.join(line.decode('utf-8') for line in list(response.streaming_content))
        self.assertIn('M42', content)
        self.assertIn('M52', content)

    def test_export_filtered_targets_with_aliases(self):
        TargetNameFactory.create(name='Messier 42', target=self.st)
        response = self.client.get(reverse('targets:export') + '?name=M42')
        content = ''.join(line.decode('utf-8') for line in list(response.streaming_content))
        self.assertIn('M42', content)
        self.assertNotIn('M52', content)


class TestTargetSearch(TestCase):
    def setUp(self):
        self.st = SiderealTargetFactory.create(name='1337target', ra=269.9983, dec=-29.0698)
        self.st_name = TargetNameFactory.create(name='M42', target=self.st)
        self.st_name2 = TargetNameFactory.create(name='Messier 42', target=self.st)

        self.target2 = SiderealTargetFactory.create(name='Target1309', ra=266.9360, dec=-35.7749)
        self.target2_name = TargetNameFactory.create(name='NGC1309', target=self.target2)
        self.target2_name2 = TargetNameFactory.create(name='PGC 012626', target=self.target2)

        self.user = User.objects.create(username='testuser')
        self.client.force_login(self.user)
        assign_perm('tom_targets.view_target', self.user, self.st)

    def test_search_name_no_results(self):
        response = self.client.get(reverse('targets:list') + '?name=noresults')
        self.assertNotContains(response, '1337target')

    def test_search_name(self):
        response = self.client.get(reverse('targets:list') + '?name=M42')
        self.assertContains(response, '1337target')
        self.assertNotContains(response, '1309Target')

        response = self.client.get(reverse('targets:list') + '?name=Messier 42')
        self.assertContains(response, '1337target')
        self.assertNotContains(response, '1309Target')

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

    def test_cone_search_coordinates(self):
        response = self.client.get(reverse('targets:list') + '?cone_search=269.75891,-29.179583,0.25')
        self.assertContains(response, '1337target')
        self.assertNotContains(response, 'Target1309')

    def test_cone_search_target(self):
        response = self.client.get(reverse('targets:list') + '?target_cone_search=1337target,1')
        self.assertContains(response, '1337target')
        self.assertNotContains(response, 'Target1309')


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
        for _ in range(3):
            ft = SiderealTargetFactory.create()
            self.fake_targets.append(ft)
            assign_perm('tom_targets.view_target', user, ft)
            assign_perm('tom_targets.change_target', user, ft)
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

        messages = [(m.message, m.level) for m in get_messages(response.wsgi_request)]
        self.assertIn(('1 target(s) successfully added to group \'{}\'.'.format(self.fake_grouping.name),
                       SUCCESS), messages)
        self.assertIn(('1 target(s) already in group \'{}\': {}'.format(
            self.fake_grouping.name, self.fake_targets[0].name), WARNING), messages)

    def test_add_to_invalid_grouping(self):
        data = {
            'grouping': -1,
            'add': True,
            'isSelectAll': 'False',
            'selected-target': self.fake_targets[1].id,
            'query_string': '',
        }
        response = self.client.post(reverse('targets:add-remove-grouping'), data=data)
        self.assertEqual(self.fake_grouping.targets.count(), 1)
        self.assertTrue(self.fake_targets[0] in self.fake_grouping.targets.all())
        messages = [(m.message, m.level) for m in get_messages(response.wsgi_request)]
        self.assertTrue('Cannot find the target group with id=-1; ' in messages[0][0])

    # Remove target[0] and [1] from grouping;
    def test_remove_selected_from_grouping(self):
        data = {
            'grouping': self.fake_grouping.id,
            'remove': True,
            'isSelectAll': 'False',
            'selected-target': [self.fake_targets[0].id, self.fake_targets[1].id],
            'query_string': '',
        }
        response = self.client.post(reverse('targets:add-remove-grouping'), data=data)
        self.assertEqual(self.fake_grouping.targets.count(), 0)
        messages = [(m.message, m.level) for m in get_messages(response.wsgi_request)]
        self.assertIn(('1 target(s) successfully removed from group \'{}\'.'.format(self.fake_grouping.name),
                       SUCCESS), messages)
        self.assertIn(('1 target(s) not in group \'{}\': {}'.format(self.fake_grouping.name, self.fake_targets[1].name),
                       WARNING), messages)

    # Add target[0] and [1] to grouping; [0] already exists and [1] new
    def test_move_selected_to_grouping(self):
        data = {
            'grouping': self.fake_grouping.id,
            'move': True,
            'isSelectAll': 'False',
            'selected-target': [self.fake_targets[0].id, self.fake_targets[1].id],
            'query_string': '',
        }
        first_grouping = TargetGroupingFactory.create()
        self.fake_targets[0].targetlist_set.add(first_grouping)
        self.fake_targets[1].targetlist_set.add(first_grouping)
        response = self.client.post(reverse('targets:add-remove-grouping'), data=data)

        self.assertEqual(self.fake_grouping.targets.count(), 2)
        self.assertTrue(self.fake_targets[0] in self.fake_grouping.targets.all())
        self.assertTrue(self.fake_targets[1] in self.fake_grouping.targets.all())
        self.assertTrue(self.fake_targets[0] in first_grouping.targets.all())
        self.assertFalse(self.fake_targets[1] in first_grouping.targets.all())

        messages = [(m.message, m.level) for m in get_messages(response.wsgi_request)]
        self.assertIn(('1 target(s) successfully moved to group \'{}\'.'.format(self.fake_grouping.name),
                       SUCCESS), messages)
        self.assertIn(('1 target(s) already in group \'{}\': {}'.format(
            self.fake_grouping.name, self.fake_targets[0].name), WARNING), messages)

    def test_move_all_to_grouping_filtered_by_sidereal(self):
        data = {
            'grouping': self.fake_grouping.id,
            'move': True,
            'isSelectAll': 'True',
            'selected-target': [],
            'query_string': 'type=SIDEREAL&name=&key=&value=&targetlist__name=',
        }
        first_grouping = TargetGroupingFactory.create()
        first_grouping.targets.add(*self.fake_targets)
        response = self.client.post(reverse('targets:add-remove-grouping'), data=data)
        self.assertEqual(self.fake_grouping.targets.count(), 3)
        self.assertEqual(first_grouping.targets.count(), 1)
        messages = [(m.message, m.level) for m in get_messages(response.wsgi_request)]
        self.assertIn(('2 target(s) successfully moved to group \'{}\'.'.format(self.fake_grouping.name),
                       SUCCESS), messages)
        self.assertIn((
            '1 target(s) already in group \'{}\': {}'.format(self.fake_grouping.name, self.fake_targets[0].name),
            WARNING), messages
        )

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
            'query_string': 'type=SIDEREAL&name=&key=&value=&targetlist__name=',
        }
        response = self.client.post(reverse('targets:add-remove-grouping'), data=data)
        self.assertEqual(self.fake_grouping.targets.count(), 3)
        messages = [(m.message, m.level) for m in get_messages(response.wsgi_request)]
        self.assertIn(('2 target(s) successfully added to group \'{}\'.'.format(self.fake_grouping.name),
                       SUCCESS), messages)
        self.assertIn((
            '1 target(s) already in group \'{}\': {}'.format(self.fake_grouping.name, self.fake_targets[0].name),
            WARNING), messages
        )

    def test_remove_all_from_grouping_filtered_by_sidereal(self):
        data = {
            'grouping': self.fake_grouping.id,
            'remove': True,
            'isSelectAll': 'True',
            'selected-target': [],
            'query_string': 'type=SIDEREAL&name=&key=&value=&targetlist__name=',
        }
        response = self.client.post(reverse('targets:add-remove-grouping'), data=data)
        self.assertEqual(self.fake_grouping.targets.count(), 0)
        messages = [(m.message, m.level) for m in get_messages(response.wsgi_request)]
        self.assertIn(('1 target(s) successfully removed from group \'{}\'.'.format(self.fake_grouping.name),
                       SUCCESS), messages)
        self.assertIn(('2 target(s) not in group \'{}\': {}'.format(
            self.fake_grouping.name, self.fake_targets[1].name + ', ' + self.fake_targets[2].name
        ), WARNING), messages)

    def test_remove_all_from_grouping_filtered_by_grouping(self):
        data = {
            'grouping': self.fake_grouping.id,
            'remove': True,
            'isSelectAll': 'True',
            'selected-target': [],
            'query_string': 'type=&name=&key=&value=&targetlist__name=' + str(self.fake_grouping.id),
        }
        response = self.client.post(reverse('targets:add-remove-grouping'), data=data)
        self.assertEqual(self.fake_grouping.targets.count(), 0)
        messages = [(m.message, m.level) for m in get_messages(response.wsgi_request)]
        self.assertIn(('1 target(s) successfully removed from group \'{}\'.'.format(self.fake_grouping.name),
                       SUCCESS), messages)

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
        response = self.client.post(reverse('targets:add-remove-grouping'), data=data)
        self.assertEqual(self.fake_grouping.targets.count(), 0)
        messages = [(m.message, m.level) for m in get_messages(response.wsgi_request)]
        self.assertIn(('1 target(s) successfully removed from group \'{}\'.'.format(self.fake_grouping.name),
                       SUCCESS), messages)
        self.assertIn(('2 target(s) not in group \'{}\': {}'.format(
            self.fake_grouping.name, self.fake_targets[1].name + ', ' + self.fake_targets[2].name
        ), WARNING), messages)

    def test_persist_filter(self):
        data = {'query_string': 'type=SIDEREAL&name=B&key=C&value=123&targetlist__name=1'}
        expected_query_dict = {
            'type': 'SIDEREAL',
            'name': 'B',
            'key': 'C',
            'value': '123',
            'targetlist__name': '1'}
        response = self.client.post(reverse('targets:add-remove-grouping'), data=data, follow=True)
        response_query_dict = response.context['filter'].data.dict()
        self.assertEqual(response_query_dict, expected_query_dict)

    def test_persist_filter_empty(self):
        expected_query_dict = {}
        response = self.client.post(reverse('targets:add-remove-grouping'), data={}, follow=True)
        response_query_dict = response.context['filter'].data
        self.assertEqual(response_query_dict, expected_query_dict)
