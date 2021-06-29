from unittest import mock

from django.test import override_settings, tag, TestCase

from tom_alerts.alerts import get_service_class
from tom_alerts.brokers.lasair import LasairBroker, LasairBrokerForm

alert1 = {
    'candidates':
    {
       'decl': 30.5462915,
       'magpsf': 15.4319,
       'ra': 52.6833968,
       'candid': 1638483221215015008,
    },
    'objectData': {
        'glonmean': 159.12011347419698,
        'glatmean': -20.911037347147648,
    },
    'objectId': 'ZTF18aaaduje',
}


class TestLasairBrokerForm(TestCase):
    def setUp(self):
        pass

    def test_clean(self):
        form_parameters = {'query_name': 'Test Lasair', 'broker': 'Lasair', 'name': 'ZTF18abbkloa',
                           'cone': '', 'sqlquery': ''}

        with self.subTest():
            form = LasairBrokerForm(form_parameters)
            self.assertFalse(form.is_valid())
            self.assertIn('One of either Object Cone Search or Freeform SQL Query must be populated.',
                          form.non_field_errors())

        test_parameters_list = [{'cone': '1, 2', 'sqlquery': ''}, {'cone': '', 'sqlquery': 'select * from objects;'}]
        for test_params in test_parameters_list:
            with self.subTest():
                form_parameters.update(test_params)
                form = LasairBrokerForm(form_parameters)
                self.assertTrue(form.is_valid())


@override_settings(TOM_ALERT_CLASSES=['tom_alerts.brokers.lasair.LasairBroker'])
class TestLasairBrokerClass(TestCase):
    """ Test the functionality of the LasairBroker, we modify the django settings to make sure
    it is the only installed broker.
    """
    def setUp(self):
        pass

    def test_get_broker_class(self):
        self.assertEqual(LasairBroker, get_service_class('Lasair'))

    @mock.patch('tom_alerts.brokers.lasair.requests.get')
    def test_fetch_alerts(self, mock_requests_get):
        pass

    @mock.patch('tom_alerts.brokers.lasair.LasairBroker.fetch_alert')
    def test_to_target(self, alert):
        testalert = alert1
        created_target = LasairBroker().to_target(testalert) #uses to_target method
        self.assertEqual(created_target.name, 'ZTF18aaaduje') #checks to_target method works with assertEqual() method

    def test_to_generic_alert(self):
        pass


@tag('canary')
class TestLasairModuleCanary(TestCase):
    def setUp(self):
        self.broker = LasairBroker()

    def test_fetch_alerts(self):
        pass

    def test_fetch_alert(self):
        pass
