from datetime import datetime, timezone
import json
from requests import Response
from unittest.mock import patch

from django.test import tag, TestCase
from faker import Faker

from tom_alerts.brokers.alerce import ALeRCEBroker, ALeRCEQueryForm
from tom_targets.models import Target


def create_alerce_alert(firstmjd=None, lastmjd=None, class_name=None, classifier=None, probability=None):
    fake = Faker()

    return {'oid': fake.pystr_format(string_format='ZTF##???????', letters='abcdefghijklmnopqrstuvwxyz'),
            'meanra': fake.pyfloat(min_value=0, max_value=360),
            'meandec': fake.pyfloat(min_value=0, max_value=360),
            'firstmjd': firstmjd if firstmjd else fake.pyfloat(min_value=56000, max_value=59000, right_digits=1),
            'lastmjd': lastmjd if lastmjd else fake.pyfloat(min_value=56000, max_value=59000, right_digits=1),
            'class': class_name if class_name else fake.pystr_format(string_format='????????',
                                                                     letters='ABCDEFGHIJKLMNOPQRSTUVWXYZ'),
            'classifier': classifier if classifier else fake.pystr_format(string_format='???',
                                                                          letters='ABCDEFGHIJKLMNOPQRSTUVWXYZ'),
            'probability': probability if probability else fake.pyfloat(min_value=0, max_value=1)}


def create_alerce_query_response(num_alerts):
    alerts = [create_alerce_alert() for i in range(0, num_alerts)]

    return {
        'total': None, 'page': 1, 'next': None, 'has_next': False, 'prev': None, 'has_prev': False,
        'items': alerts
    }


class TestALeRCEBrokerForm(TestCase):
    def setUp(self):
        self.base_form_data = {
            'query_name': 'Test Query',
            'broker': 'ALeRCE'
        }

    def test_cone_search_validation(self):
        """Test cross-field validation for cone search filters."""

        # Test that validation fails if not all fields are present
        parameters_list = [
            {'ra': 10, 'dec': 10}, {'dec': 10, 'radius': 10}, {'ra': 10, 'radius': 10}
        ]
        for parameters in parameters_list:
            with self.subTest():
                parameters.update(self.base_form_data)
                form = ALeRCEQueryForm(parameters)
                self.assertFalse(form.is_valid())
                self.assertIn('All of RA, Dec, and Search Radius must be included to execute a cone search.',
                              form.non_field_errors())

        # Test that validation passes when all three fields are present
        self.base_form_data.update({'ra': 10, 'dec': 10, 'radius': 10})
        form = ALeRCEQueryForm(self.base_form_data)
        self.assertTrue(form.is_valid())

    def test_time_filters_validation(self):
        """Test validation for time filters."""

        # Test that mjd__lt and mjd__gt fail when mjd__lt is less than mjd__gt
        with self.subTest():
            parameters = {'lastmjd': 57000, 'firstmjd': 57001}
            parameters.update(self.base_form_data)
            form = ALeRCEQueryForm(parameters)
            self.assertFalse(form.is_valid())
            self.assertIn('Min date of first detection must be earlier than max date of first detection.',
                          form.non_field_errors())

        # Test that form validation succeeds when relative time fields make sense and absolute time field is used alone.
        parameters_list = [
            {'firstmjd': 57000, 'lastmjd': 58000},
        ]
        for parameters in parameters_list:
            with self.subTest():
                parameters.update(self.base_form_data)
                form = ALeRCEQueryForm(parameters)
                self.assertTrue(form.is_valid())


class TestALeRCEBrokerClass(TestCase):
    def setUp(self):
        self.base_form_data = {
            'query_name': 'Test ALeRCE',
            'broker': 'ALeRCE',
        }
        self.broker = ALeRCEBroker()

    def test_clean_coordinate_parameters(self):
        """Test that _clean_date_parameters results in the correct dict structure."""
        parameters_list = [
            ({'ra': 10, 'dec': 10, 'radius': None}, {}),
            ({'ra': 10, 'dec': 10, 'radius': 10}, {'ra': 10, 'dec': 10, 'radius': 10})
        ]
        for parameters, expected in parameters_list:
            with self.subTest():
                self.assertDictEqual(self.broker._clean_coordinate_parameters(parameters), expected)

    def test_clean_date_parameters(self):
        """Test that _clean_date_parameters results in the correct dict structure."""
        parameters_list = [
            ({'firstmjd': 57000, 'lastmjd': 58000}, {'firstmjd': 57000, 'lastmjd': 58000}),
            ({'firstmjd': 57000, 'lastmjd': None}, {'firstmjd': 57000}),
            ({'firstmjd': None, 'lastmjd': None}, {})
        ]
        for parameters, expected in parameters_list:
            with self.subTest():
                self.assertDictEqual(self.broker._clean_date_parameters(parameters), expected)

    def test_clean_classifier_parameters(self):
        """Test that _clean_filter_parameters results in the correct dict structure."""

        # Test that classifiers are populated correctly
        parameters_list = [
            ({'stamp_classifier': None, 'p_stamp_classifier': None, 'lc_classifier': None, 'p_lc_classifier': None},
             {}),
            ({'stamp_classifier': 'SN', 'p_stamp_classifier': None, 'lc_classifier': None, 'p_lc_classifier': None},
             {'classifier': 'stamp_classifier', 'class': 'SN'}),
            ({'stamp_classifier': 'SN', 'p_stamp_classifier': 0.5, 'lc_classifier': None, 'p_lc_classifier': None},
             {'classifier': 'stamp_classifier', 'class': 'SN', 'probability': 0.5}),
            ({'stamp_classifier': None, 'p_stamp_classifier': None, 'lc_classifier': 'SNIa', 'p_lc_classifier': None},
             {'classifier': 'lc_classifier', 'class': 'SNIa'}),
            ({'stamp_classifier': None, 'p_stamp_classifier': None, 'lc_classifier': 'SNIa', 'p_lc_classifier': 0.5},
             {'classifier': 'lc_classifier', 'class': 'SNIa', 'probability': 0.5}),
        ]
        for parameters, expected in parameters_list:
            with self.subTest():
                self.assertDictEqual(expected, self.broker._clean_classifier_parameters(parameters))

    @patch('tom_alerts.brokers.alerce.ALeRCEBroker._clean_classifier_parameters')
    @patch('tom_alerts.brokers.alerce.ALeRCEBroker._clean_date_parameters')
    @patch('tom_alerts.brokers.alerce.ALeRCEBroker._clean_coordinate_parameters')
    def test_clean_parameters(self, mock_coordinate, mock_date, mock_classifier):
        mock_coordinate.return_value = {'ra': 10, 'dec': 10, 'radius': 10}
        mock_date.return_value = {'firstmjd': 57000, 'lastmjd': 58000}
        mock_classifier.return_value = {'classifier': 'stamp_classifier', 'class': 'SN', 'probability': 0.5}

        # Ensure that passed in values are used to populate the payload
        parameters = {'page': 2}
        payload = self.broker._clean_parameters(parameters)
        with self.subTest():
            self.assertEqual(payload['page'], parameters['page'])
            self.assertEqual(payload['page_size'], 20)
            for k in ['ra', 'dec', 'radius', 'firstmjd', 'lastmjd', 'classifier', 'class', 'probability']:
                self.assertIn(k, payload.keys())

        # Ensure that missing values result in default values being used to populate the payload
        payload = self.broker._clean_parameters({})
        with self.subTest():
            self.assertEqual(payload['page'], 1)

    @patch('tom_alerts.brokers.alerce.requests.get')
    @patch('tom_alerts.brokers.alerce.ALeRCEBroker._clean_parameters')
    def test_fetch_alerts(self, mock_clean_parameters, mock_requests_post):
        """Test fetch_alerts broker method."""
        mock_response = Response()
        mock_response_content = create_alerce_query_response(25)
        # TODO: without setting 'page' to a value greater than 1, an infinite recursion depth error occurs.
        # This should be addressed when there isn't a demo in 24 hours.
        mock_response_content['page'] = 2
        mock_response._content = str.encode(json.dumps(mock_response_content))
        mock_response.status_code = 200
        mock_requests_post.return_value = mock_response

        response = self.broker.fetch_alerts({})
        alerts = []
        for alert in response:
            alerts.append(alert)
        self.assertEqual(25, len(alerts))

        self.assertEqual(alerts[0], mock_response_content['items'][0])

    @patch('tom_alerts.brokers.alerce.requests.get')
    def test_fetch_alert(self, mock_requests_post):
        """Test fetch_alert broker method."""
        alert = create_alerce_alert(1)
        mock_response = Response()
        mock_response_content = alert
        mock_response._content = str.encode(json.dumps(mock_response_content))
        mock_response.status_code = 200
        mock_requests_post.return_value = mock_response

        alert_response = self.broker.fetch_alert(alert['oid'])
        self.assertDictEqual(alert_response, alert)

    def test_to_target(self):
        """Test to_target broker method."""
        mock_alert = create_alerce_alert()
        self.broker.to_target(mock_alert)
        t = Target.objects.first()

        self.assertEqual(mock_alert['oid'], t.name)
        self.assertEqual(mock_alert['meanra'], t.ra)
        self.assertEqual(mock_alert['meandec'], t.dec)

    def test_to_generic_alert(self):
        """Test to_generic_alert broker method."""

        # Test that timestamp is populated correctly.
        mock_alert = create_alerce_alert()
        mock_alert['lastmjd'] = None
        self.assertEqual('', self.broker.to_generic_alert(mock_alert).timestamp)

        mock_alert = create_alerce_alert(lastmjd=59155)
        self.assertEqual(datetime(2020, 11, 2, tzinfo=timezone.utc),
                         self.broker.to_generic_alert(mock_alert).timestamp)

        # Test that the url is created properly.
        mock_alert = create_alerce_alert()
        self.assertEqual(f'https://alerce.online/object/{mock_alert["oid"]}',
                         self.broker.to_generic_alert(mock_alert).url)

        # Test that the classification is selected correctly
        mock_alert = create_alerce_alert()
        self.assertEqual(mock_alert['probability'], self.broker.to_generic_alert(mock_alert).score)

        mock_alert = create_alerce_alert()
        mock_alert['probability'] = None
        self.assertEqual(None, self.broker.to_generic_alert(mock_alert).score)


@tag('canary')
class TestALeRCEModuleCanary(TestCase):
    def setUp(self):
        self.broker = ALeRCEBroker()

    @patch('tom_alerts.brokers.alerce.cache.get')
    def test_get_classifiers(self, mock_cache_get):
        mock_cache_get.return_value = None  # Ensure cache is not used

        expected_classifiers = ['lc_classifier', 'stamp_classifier']
        classifiers = ALeRCEQueryForm._get_classifiers()
        for expected in expected_classifiers:
            for classifier in classifiers:
                if expected == classifier['classifier_name']:
                    break
            else:
                self.fail(f'Did not find {expected} in classifiers.')

    def test_fetch_alerts(self):
        form = ALeRCEQueryForm({'query_name': 'Test', 'broker': 'ALeRCE', 'ndet': 1, 'classifier': 'stamp_classifier',
                                'class': 'SN', 'probability': 0.7, 'mjd__gt': 59148.78219219812})
        form.is_valid()
        query = form.save()

        alerts = [alert for alert in self.broker.fetch_alerts(query.parameters)]

        self.assertGreaterEqual(len(alerts), 6)
        for k in ['oid', 'firstmjd', 'lastmjd', 'class', 'classifier', 'probability', 'meanra', 'meandec']:
            self.assertIn(k, alerts[0])

    def test_fetch_alert(self):
        """
        Test fetching a single alert from ALeRCE. The two response values tested are the only ones that are not derived,
        and are therefore consistent.
        """
        alert = self.broker.fetch_alert('ZTF20acnsdjd')

        self.assertDictContainsSubset({
            'oid': 'ZTF20acnsdjd',
            'firstmjd': 59149.1119328998,
        }, alert)
