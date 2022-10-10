import json
from unittest.mock import patch

from django import forms
from django.contrib.auth.models import User, Group
from django.contrib.messages import get_messages
from django.core.cache import cache
from django.test import TestCase, override_settings
from django.urls import reverse

from tom_alerts.alerts import GenericBroker, GenericQueryForm, GenericUpstreamSubmissionForm, GenericAlert
from tom_alerts.alerts import get_service_class, get_service_classes
from tom_alerts.exceptions import AlertSubmissionException
from tom_alerts.models import BrokerQuery
from tom_observations.models import ObservationRecord
from tom_targets.models import Target

# Test alert data. Normally this would come from a remote source.
test_alerts = [
    {'id': 1, 'name': 'Tatooine', 'timestamp': '2019-07-01', 'ra': 32, 'dec': -20, 'mag': 8, 'score': 20},
    {'id': 2, 'name': 'Hoth', 'timestamp': '2019-07-02', 'ra': 66, 'dec': 50, 'mag': 3, 'score': 66},
]


class TestBrokerForm(GenericQueryForm):
    """ All brokers must have a form which will be used to construct and save queries
    to the broker. They should subclass `GenericQueryForm` which includes some required
    fields and contains logic for serializing and persisting the query parameters to the
    database. This test form will only have one field.
    """
    name = forms.CharField(required=True)


class TestUpstreamSubmissionForm(GenericUpstreamSubmissionForm):
    """
    Brokers supporting upstream submission can have a form used for constructing the submission. If should subclass
    GenericUpstreamSubmissionForm. This test form will have only one additional field in order to test that the
    additional field value is submitted to the broker correctly.
    """
    topic = forms.CharField(required=False)


class TestBroker(GenericBroker):
    """ The broker class encapsulates the logic for querying remote brokers and transforming
    the returned data into TOM Toolkit Targets so they can be used elsewhere in the system. The
    following methods and attributes are all required, but a broker can be as complex as needed.
    """
    name = 'TEST'  # The name of this broker.
    form = TestBrokerForm  # The form that will be used to write and save queries.
    alert_submission_form = TestUpstreamSubmissionForm

    def fetch_alerts(self, parameters):
        """ All brokers must implement this method. It must return a list of alerts and may include broker feedback.
        """
        # Here we simply return a list of `GenericAlert`s that match the name passed in via `parameters`.
        return iter([alert for alert in test_alerts if alert['name'] == parameters['name']]), "test message"

    def no_message_fetch_alerts(self, parameters):
        """ Older brokers might implement this version of the fetch_alerts method. It returns a list of alerts.
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

    def submit_upstream_alert(self, target=None, observation_record=None, **kwargs):
        return super().submit_upstream_alert(target=target, observation_record=observation_record)


@override_settings(TOM_ALERT_CLASSES=['tom_alerts.tests.tests.TestBroker'])
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
        alerts, _ = TestBroker().fetch_alerts({'name': 'Hoth'})
        self.assertEqual(test_alerts[1], list(alerts)[0])

    def test_old_fetch_alerts(self):
        alerts = TestBroker().no_message_fetch_alerts({'name': 'Hoth'})
        self.assertFalse(isinstance(alerts, tuple))
        self.assertEqual(test_alerts[1], list(alerts)[0])

    def test_to_generic_alert(self):
        ga = TestBroker().to_generic_alert(test_alerts[0])
        self.assertEqual(ga.name, test_alerts[0]['name'])

    def test_to_target(self):
        target, _, _ = TestBroker().to_generic_alert(test_alerts[0]).to_target()
        self.assertEqual(target.name, test_alerts[0]['name'])


@override_settings(TOM_ALERT_CLASSES=['tom_alerts.fake_broker'])
class TestAlertModule(TestCase):
    """Test that attempting to import a nonexistent broker module raises the appropriate errors.
    """

    def test_get_service_classes_import_error(self):
        with self.subTest('Invalid import returns an import error.'):
            with patch('tom_alerts.alerts.import_module') as mock_import_module:
                mock_import_module.side_effect = ImportError()
                with self.assertRaisesRegex(ImportError, 'Could not import tom_alerts.fake_broker.'):
                    get_service_classes()

        with self.subTest('Invalid import returns an attribute error.'):
            with patch('tom_alerts.alerts.import_module') as mock_import_module:
                mock_import_module.side_effect = AttributeError()
                with self.assertRaisesRegex(ImportError, 'Could not import tom_alerts.fake_broker.'):
                    get_service_classes()


@override_settings(TOM_ALERT_CLASSES=['tom_alerts.tests.tests.TestBroker'])
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
            parameters={'name': 'Alderaan'},
        )
        not_found = BrokerQuery.objects.create(
            name='find hoth',
            broker='TEST',
            parameters={'name': 'Hoth'},
        )
        response = self.client.get(reverse('tom_alerts:list') + '?name=dust')
        self.assertContains(response, broker_query.name)
        self.assertNotContains(response, not_found.name)

    def test_delete_query(self):
        broker_query = BrokerQuery.objects.create(
            name='find hoth',
            broker='TEST',
            parameters={'name': 'Hoth'},
        )
        self.assertTrue(BrokerQuery.objects.filter(name='find hoth').exists())
        self.client.post(reverse('tom_alerts:delete', kwargs={'pk': broker_query.id}))
        self.assertFalse(BrokerQuery.objects.filter(name='find hoth').exists())

    def test_run_query(self):
        broker_query = BrokerQuery.objects.create(
            name='find hoth',
            broker='TEST',
            parameters={'name': 'Hoth'},
        )
        response = self.client.get(reverse('tom_alerts:run', kwargs={'pk': broker_query.id}))
        self.assertContains(response,  '66')

    def test_update_query(self):
        broker_query = BrokerQuery.objects.create(
            name='find hoth',
            broker='TEST',
            parameters={'name': 'Hoth'},
        )
        update_data = {
            'query_name': 'find hoth',
            'broker': 'TEST',
            'name': 'another place',
        }
        self.client.post(reverse('tom_alerts:update', kwargs={'pk': broker_query.id}), data=update_data)
        broker_query.refresh_from_db()
        self.assertEqual(broker_query.parameters['name'], update_data['name'])

    @override_settings(CACHES={
            'default': {
                'BACKEND': 'django.core.cache.backends.locmem.LocMemCache',
            }
        })
    def test_create_target(self):
        cache.set('alert_2', json.dumps(test_alerts[1]))
        query = BrokerQuery.objects.create(
            name='find hoth',
            broker='TEST',
            parameters={'name': 'Hoth'},
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
        cache.set('alert_1', json.dumps(test_alerts[0]))
        cache.set('alert_2', json.dumps(test_alerts[1]))
        query = BrokerQuery.objects.create(
            name='find anything',
            broker='TEST',
            parameters={'score__gt': 19},
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
            parameters={'name': 'Alderaan'},
        )
        post_data = {
            'broker': 'TEST',
            'query_id': query.id,
            'alerts': []
        }
        response = self.client.post(reverse('tom_alerts:create-target'), data=post_data, follow=True)
        self.assertEqual(Target.objects.count(), 0)
        self.assertRedirects(response, reverse('tom_alerts:run', kwargs={'pk': query.id}))

    @patch('tom_alerts.tests.tests.TestBroker.submit_upstream_alert')
    def test_submit_alert_success(self, mock_submit_upstream_alert):
        """Test submission of an alert to a broker."""

        # Tests that an alert is submitted with just a target, and that no redirect_url results in redirect to home
        target = Target.objects.create(name='test_target', ra=1, dec=2)
        response = self.client.post(reverse('tom_alerts:submit-alert', kwargs={'broker': 'TEST'}),
                                    data={'target': target.id})

        mock_submit_upstream_alert.assert_called_with(target=target, observation_record=None, topic='')
        self.assertEqual(response.status_code, 302)
        self.assertRedirects(response, reverse('home'))

        # Tests that an alert is submitted with just an observation, and that redirect is to redirect_url
        obsr = ObservationRecord.objects.create(target=target, facility='Test', parameters={}, observation_id=1)
        response = self.client.post(reverse('tom_alerts:submit-alert', kwargs={'broker': 'TEST'}),
                                    data={'observation_record': obsr.id, 'redirect_url': reverse('tom_targets:list')})

        mock_submit_upstream_alert.assert_called_with(target=None, observation_record=obsr, topic='')
        self.assertEqual(response.status_code, 302)
        self.assertRedirects(response, reverse('tom_targets:list'))

        # Tests that an alert submitted with additional parameters calls submit_upstream_alert correctly.
        response = self.client.post(reverse('tom_alerts:submit-alert', kwargs={'broker': 'TEST'}),
                                    data={'observation_record': obsr.id, 'topic': 'test topic'})
        mock_submit_upstream_alert.assert_called_with(target=None, observation_record=obsr, topic='test topic')

    @patch('tom_alerts.tests.tests.TestBroker.submit_upstream_alert')
    def test_submit_alert_failure(self, mock_submit_upstream_alert):
        """Test that a failed alert submission returns an appropriate message."""
        target = Target.objects.create(name='test_target', ra=1, dec=2)
        mock_submit_upstream_alert.return_value = False
        response = self.client.post(reverse('tom_alerts:submit-alert', kwargs={'broker': 'TEST'}),
                                    data={'target': target.id})
        messages = [(m.message, m.level) for m in get_messages(response.wsgi_request)]
        self.assertEqual(len(messages), 1)
        self.assertEqual(messages[0][0], 'Unable to submit one or more alerts to TEST. See logs for details.')

    @patch('tom_alerts.tests.tests.TestBroker.submit_upstream_alert')
    def test_submit_alert_exception(self, mock_submit_upstream_alert):
        """Test that an alert submission returns an appropriate message when alert submission raises an exception."""
        mock_submit_upstream_alert.side_effect = AlertSubmissionException()

        response = self.client.post(reverse('tom_alerts:submit-alert', kwargs={'broker': 'TEST'}), data={})
        messages = [(m.message, m.level) for m in get_messages(response.wsgi_request)]
        self.assertEqual(len(messages), 1)
        self.assertEqual(messages[0][0], 'Unable to submit one or more alerts to TEST. See logs for details.')

    def test_submit_alert_invalid_form(self):
        """Test that an alert submission failed when form is invalid."""
        response = self.client.post(reverse('tom_alerts:submit-alert', kwargs={'broker': 'TEST'}), data={})
        messages = [(m.message, m.level) for m in get_messages(response.wsgi_request)]
        self.assertEqual(len(messages), 1)
        self.assertEqual(messages[0][0], 'Unable to submit one or more alerts to TEST. See logs for details.')
        self.assertRedirects(response, reverse('home'))
