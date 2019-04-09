from django.test import TestCase, override_settings
from django import forms
from datetime import datetime
from django.contrib.auth.models import User, Group
from django.urls import reverse

from tom_alerts.alerts import GenericQueryForm, GenericAlert, get_service_class
from tom_alerts.models import BrokerQuery
from tom_targets.models import Target

# Test alert data. Normally this would come from a remote source.
test_alerts = [
    {'id': 1, 'name': 'Tatooine', 'timestamp': datetime.utcnow(), 'ra': 32, 'dec': -20, 'mag': 8, 'score': 20},
    {'id': 2, 'name': 'Hoth', 'timestamp': datetime.utcnow(), 'ra': 66, 'dec': 50, 'mag': 3, 'score': 66},
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
        return [alert for alert in test_alerts if alert['name'] == parameters['name']]

    def fetch_alert(self, alert_id):
        """ Method to retrieve and return a single alert.
        """
        for alert in test_alerts:
            if alert['id'] == int(alert_id):
                return alert
        return None

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
        """ Transform a single alert into a `Target`, so that it can be used in the rest of the TOM.
        """
        return Target(
            identifier=alert['id'],
            name=alert['name'],
            type='SIDEREAL',
            ra=alert['ra'],
            dec=alert['dec'],
        )


@override_settings(TOM_ALERT_CLASSES=['tom_alerts.tests.tests_generic.TestBroker'])
class TestBrokerClass(TestCase):
    """ Test the functionality of the TestBroker, we modify the django settings to make sure
    it is the only installed broker.
    """
    def test_get_broker_class(self):
        self.assertEqual(TestBroker, get_service_class('TEST'))

    def test_get_invalid_broker(self):
        with self.assertRaises(ImportError):
            get_service_class('MARS')

    def test_fetch_alerts(self):
        alerts = TestBroker().fetch_alerts({'name': 'Hoth'})
        self.assertEqual(test_alerts[1], alerts[0])

    def test_fetch_alert(self):
        alert = TestBroker().fetch_alert(1)
        self.assertEqual(test_alerts[0], alert)

    def test_to_generic_alert(self):
        ga = TestBroker().to_generic_alert(test_alerts[0])
        self.assertEqual(ga.name, test_alerts[0]['name'])

    def test_to_target(self):
        target = TestBroker().to_target(test_alerts[0])
        self.assertEqual(target.name, test_alerts[0]['name'])


@override_settings(TOM_ALERT_CLASSES=['tom_alerts.tests.tests_generic.TestBroker'])
class TestBrokerViews(TestCase):
    """ Test the views that use the broker classes
    """
    def setUp(self):
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

    def test_create_target(self):
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

    def test_create_multiple_targets(self):
        query = BrokerQuery.objects.create(
            name='find anything',
            broker='TEST',
            parameters='{"score__gt": "19"}'
        )
        post_data = {
            'broker': 'TEST',
            'query_id': query.id,
            'alerts': [1, 2]
        }
        response = self.client.post(reverse('tom_alerts:create-target'), data=post_data)
        self.assertEqual(Target.objects.count(), 2)
        self.assertRedirects(response, reverse('tom_targets:list'))

    def test_create_no_targets(self):
        query = BrokerQuery.objects.create(
            name='find anything',
            broker='TEST',
            parameters='{"name": "Alderaan"}'
        )
        post_data = {
            'broker': 'TEST',
            'query_id': query.id,
            'alerts': []
        }
        response = self.client.post(reverse('tom_alerts:create-target'), data=post_data, follow=True)
        self.assertEqual(Target.objects.count(), 0)
        self.assertRedirects(response, reverse('tom_alerts:run', kwargs={'pk': query.id}))
