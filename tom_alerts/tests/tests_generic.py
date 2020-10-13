import json

from django import forms
from django.contrib.auth.models import User, Group
from django.core.cache import cache
from django.db import IntegrityError, transaction
from django.test import TestCase, override_settings
from django.urls import reverse

from tom_alerts.alerts import GenericQueryForm, GenericAlert, get_service_class
from tom_alerts.models import BrokerQuery
from tom_targets.models import Target, TargetExtra, TargetName


# Test alert data. Normally this would come from a remote source.
test_alerts = [
    {'id': 1, 'name': 'Tatooine', 'timestamp': '2019-07-01', 'ra': 32, 'dec': -20, 'mag': 8,
     'score': 20, 'testextra': 'testvalue', 'alias': 'testalias'},
    {'id': 2, 'name': 'Hoth', 'timestamp': '2019-07-02', 'ra': 66, 'dec': 50, 'mag': 3,
     'score': 66, 'testextra': 'testvalue', 'alias': 'testalias'},
]


class TestBrokerForm(GenericQueryForm):
    """ All brokers must have a form which will be used to construct and save queries
    to the broker. They should sublcass `GenericQueryForm` which includes some required
    fields and contains logic for serializing and persisting the query parameters to the
    database. This test form will only have one field.
    """
    name = forms.CharField(required=True)


class TestBroker:
    """ The broker class encapsulates the logic for querying remote brokers and transforming
    the returned data into TOM Toolkit Targets so they can be used elsewhere in the system. The
    following methods and attributes are all required, but a broker can be as complex as needed.
    """
    name = 'TEST'  # The name of this broker.
    form = TestBrokerForm  # The form that will be used to write and save queries.

    def fetch_alerts(self, parameters):
        """ All brokers must implement this method. It must return a list of alerts.
        """
        # Here we simply return a list of `GenericAlert`s that match the name passed in via `parameters`.
        return iter([alert for alert in test_alerts if alert['name'] == parameters['name']])

    def process_reduced_data(self, target, alert=None):
        pass

    def to_generic_alert(self, alert):
        """ We use this method to transform a remote alert (in this case an item
        from the `test_alerts` list) into a `GenericAlert` so they can be displayed in a
        consistent manner.
        """
        return GenericAlert(
            timestamp=alert['timestamp'],
            url='https://tomtoolkit.github.io',
            id=alert['id'],
            name=alert['name'],
            ra=alert['ra'],
            dec=alert['dec'],
            mag=alert['mag'],
            score=alert['score']
        )

    def to_target(self, alert):
        return Target(
            name=alert['name'],
            type='SIDEREAL',
            ra=alert['ra'],
            dec=alert['dec']
        ), [TargetExtra(key='testkey', value=alert['testextra'])], [TargetName(name=alert['alias'])]


@override_settings(TOM_ALERT_CLASSES=['tom_alerts.tests.tests_generic.TestBroker'])
class TestBrokerClass(TestCase):
    """ Test the functionality of the TestBroker, we modify the django settings to make sure
    it is the only installed broker.
    """
    def setUp(self):
        # Test alert data. Normally this would come from a remote source.
        self.test_alerts = [
            {'id': 1, 'name': 'Tatooine', 'timestamp': '2019-07-01', 'ra': 32, 'dec': -20, 'mag': 8,
             'score': 20, 'testextra': 'testvalue', 'alias': 'testalias'},
            {'id': 2, 'name': 'Hoth', 'timestamp': '2019-07-02', 'ra': 66, 'dec': 50, 'mag': 3,
             'score': 66, 'testextra': 'testvalue', 'alias': 'testalias2'},
        ]

    def test_get_broker_class(self):
        self.assertEqual(TestBroker, get_service_class('TEST'))

    def test_get_invalid_broker(self):
        with self.assertRaises(ImportError):
            get_service_class('MARS')

    def test_fetch_alerts(self):
        alerts = TestBroker().fetch_alerts({'name': 'Hoth'})
        self.assertEqual(self.test_alerts[1], list(alerts)[0])

    def test_to_generic_alert(self):
        ga = TestBroker().to_generic_alert(test_alerts[0])
        self.assertEqual(ga.name, self.test_alerts[0]['name'])

    def test_to_target(self):
        target, _, _ = TestBroker().to_target(test_alerts[0])
        self.assertEqual(target.name, self.test_alerts[0]['name'])


@override_settings(TOM_ALERT_CLASSES=['tom_alerts.tests.tests_generic.TestBroker'])
class TestBrokerViews(TestCase):
    """ Test the views that use the broker classes
    """
    def setUp(self):
        # Test alert data. Normally this would come from a remote source.
        self.test_alerts = [
            {'id': 1, 'name': 'Tatooine', 'timestamp': '2019-07-01', 'ra': 32, 'dec': -20, 'mag': 8,
             'score': 20, 'testextra': 'testvalue', 'alias': 'testalias'},
            {'id': 2, 'name': 'Hoth', 'timestamp': '2019-07-02', 'ra': 66, 'dec': 50, 'mag': 3,
             'score': 66, 'testextra': 'testvalue', 'alias': 'testalias2'},
        ]

        self.user = User.objects.create(username='Han', email='han@example.com')
        group = Group.objects.create(name='test')
        group.user_set.add(self.user)
        group.save()
        self.client.force_login(self.user)

    def test_display_form(self):
        response = self.client.get(reverse('tom_alerts:create') + '?broker=TEST')
        self.assertContains(response, 'TEST Query Form')

    def test_create_query(self):
        query_data = {
            'query_name': 'Test Query',
            'broker': 'TEST',
            'name': 'Test Name',
        }
        response = self.client.post(reverse('tom_alerts:create'), data=query_data, follow=True)
        self.assertContains(response, query_data['query_name'])
        self.assertEqual(BrokerQuery.objects.count(), 1)
        self.assertEqual(BrokerQuery.objects.first().name, query_data['query_name'])

    def test_filter_queries(self):
        broker_query = BrokerQuery.objects.create(
            name='Is it dust?',
            broker='TEST',
            parameters='{"name": "Alderaan"}',
        )
        not_found = BrokerQuery.objects.create(
            name='find hoth',
            broker='TEST',
            parameters='{"name": "Hoth"}',
        )
        response = self.client.get(reverse('tom_alerts:list') + '?name=dust')
        self.assertContains(response, broker_query.name)
        self.assertNotContains(response, not_found.name)

    def test_delete_query(self):
        broker_query = BrokerQuery.objects.create(
            name='find hoth',
            broker='TEST',
            parameters='{"name": "Hoth"}',
        )
        self.assertTrue(BrokerQuery.objects.filter(name='find hoth').exists())
        self.client.post(reverse('tom_alerts:delete', kwargs={'pk': broker_query.id}))
        self.assertFalse(BrokerQuery.objects.filter(name='find hoth').exists())

    def test_run_query(self):
        broker_query = BrokerQuery.objects.create(
            name='find hoth',
            broker='TEST',
            parameters='{"name": "Hoth"}',
        )
        response = self.client.get(reverse('tom_alerts:run', kwargs={'pk': broker_query.id}))
        self.assertContains(response,  '66')

    def test_update_query(self):
        broker_query = BrokerQuery.objects.create(
            name='find hoth',
            broker='TEST',
            parameters='{"name": "Hoth"}',
        )
        update_data = {
            'query_name': 'find hoth',
            'broker': 'TEST',
            'name': 'another place',
        }
        self.client.post(reverse('tom_alerts:update', kwargs={'pk': broker_query.id}), data=update_data)
        broker_query.refresh_from_db()
        self.assertEqual(broker_query.parameters_as_dict['name'], update_data['name'])

    @override_settings(CACHES={
            'default': {
                'BACKEND': 'django.core.cache.backends.locmem.LocMemCache',
            }
        })
    def test_create_target(self):
        # TODO: test that this creates aliases/extras
        cache.set('alert_2', json.dumps(self.test_alerts[1]))
        query = BrokerQuery.objects.create(
            name='find hoth',
            broker='TEST',
            parameters='{"name": "Hoth"}',
        )
        post_data = {
            'broker': 'TEST',
            'query_id': query.id,
            'alerts': [2]
        }
        response = self.client.post(reverse('tom_alerts:create-target'), data=post_data)
        self.assertEqual(Target.objects.count(), 1)
        self.assertEqual(Target.objects.first().name, 'Hoth')
        self.assertRedirects(response, reverse('tom_targets:update', kwargs={'pk': Target.objects.first().id}))

    @override_settings(CACHES={
            'default': {
                'BACKEND': 'django.core.cache.backends.locmem.LocMemCache',
            }
        })
    def test_create_multiple_targets(self):
        cache.set('alert_1', json.dumps(self.test_alerts[0]))
        cache.set('alert_2', json.dumps(self.test_alerts[1]))
        query = BrokerQuery.objects.create(
            name='find anything',
            broker='TEST',
            parameters='{"score__gt": "19"}',
        )
        post_data = {
            'broker': 'TEST',
            'query_id': query.id,
            'alerts': [1, 2]
        }
        response = self.client.post(reverse('tom_alerts:create-target'), data=post_data)
        self.assertEqual(Target.objects.all().count(), 2)
        self.assertRedirects(response, reverse('tom_targets:list'))

    def test_create_conflicting_targets(self):
        self.test_alerts[1]['alias'] = 'testalias'
        cache.set('alert_1', json.dumps(self.test_alerts[0]))
        cache.set('alert_2', json.dumps(self.test_alerts[1]))
        query = BrokerQuery.objects.create(
            name='find anything',
            broker='TEST',
            parameters='{"score__gt": "19"}',
        )
        post_data = {
            'broker': 'TEST',
            'query_id': query.id,
            'alerts': [1, 2]
        }
        try:
            with transaction.atomic():
                response = self.client.post(reverse('tom_alerts:create-target'), data=post_data)
            self.fail('Duplicate target created.')
        except IntegrityError:
            pass

        messages = list(response.context['messages'])
        self.assertEqual(Target.objects.all().count(), 1)
        self.assertEqual(str(messages[0]),
                         f"Unable to save {self.test_alerts[1]['name']}, target with that name already exists.")
        self.assertRedirects(response, reverse('tom_targets:list'))

    def test_create_no_targets(self):
        query = BrokerQuery.objects.create(
            name='find anything',
            broker='TEST',
            parameters='{"name": "Alderaan"}',
        )
        post_data = {
            'broker': 'TEST',
            'query_id': query.id,
            'alerts': []
        }
        response = self.client.post(reverse('tom_alerts:create-target'), data=post_data, follow=True)
        self.assertEqual(Target.objects.count(), 0)
        self.assertRedirects(response, reverse('tom_alerts:run', kwargs={'pk': query.id}))
