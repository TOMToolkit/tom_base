from datetime import datetime, timezone
import json
from requests import Response
from unittest.mock import patch

from django.test import tag, TestCase
from faker import Faker

from tom_alerts.brokers.alerce import ALeRCEBroker, ALeRCEQueryForm
from tom_targets.models import Target


alerce_classifiers_response = [
    {
        'classifier_name': 'lc_classifier',
        'classifier_version': 'hierarchical_random_forest_1.0.0',
        'classes': ['SNIa', 'QSO', 'LPV']
    },
    {
        'classifier_name': 'lc_classifier_top',
        'classifier_version': 'hierarchical_random_forest_1.0.0',
        'classes': ['Transient', 'Stochastic', 'Periodic']
    },
    {
        'classifier_name': 'lc_classifier_transient',
        'classifier_version': 'hierarchical_random_forest_1.0.0',
        'classes': ['SNIa']
    },
    {
        'classifier_name': 'lc_classifier_stochastic',
        'classifier_version': 'hierarchical_random_forest_1.0.0',
        'classes': ['QSO']
    },
    {
        'classifier_name': 'lc_classifier_periodic',
        'classifier_version': 'hierarchical_random_forest_1.0.0',
        'classes': ['LPV']
    },
    {
        'classifier_name': 'stamp_classifier',
        'classifier_version': 'stamp_classifier_1.0.4',
        'classes': ['SN']
    },
]


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


def create_alerce_query_response(num_alerts, page=1):
    alerts = [create_alerce_alert() for i in range(0, num_alerts)]

    return {
        'total': None, 'page': page, 'next': None, 'has_next': False, 'prev': None, 'has_prev': False,
        'items': alerts
    }


class TestALeRCEBrokerForm(TestCase):
    def setUp(self):
        self.base_form_data = {
            'query_name': 'Test Query',
            'broker': 'ALeRCE'
        }

    @patch('tom_alerts.brokers.alerce.cache')
    def test_cone_search_validation(self, mock_cache):
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

    @patch('tom_alerts.brokers.alerce.cache')
    def test_time_filters_validation(self, mock_cache):
        """Test validation for time filters."""

        # Test that form validation succeeds when relative time fields make sense.
        parameters_list = [
            {'firstmjd__gt': 57000, 'firstmjd__lt': 58000, 'lastmjd__gt': 58000, 'lastmjd__lt': 59000},
        ]
        for parameters in parameters_list:
            with self.subTest():
                parameters.update(self.base_form_data)
                form = ALeRCEQueryForm(parameters)
                self.assertTrue(form.is_valid())

    @patch('tom_alerts.brokers.alerce.cache.get')
    def test_classifier_filters_validation(self, mock_cache_get):
        mock_cache_get.return_value = alerce_classifiers_response

        parameters_list = [
            {'lc_classifier': 'SNIa', 'p_lc_classifier': 0.5},
            {'stamp_classifier': 'SN', 'p_stamp_classifier': 0.5}
        ]
        for parameters in parameters_list:
            with self.subTest():
                parameters.update(self.base_form_data)
                form = ALeRCEQueryForm(parameters)
                form.is_valid()
                self.assertTrue(form.is_valid())

        invalid_parameters_list = [
            {'lc_classifier': 'SNIa', 'p_stamp_classifier': 0.5},
            {'stamp_classifier': 'SN', 'p_lc_classifier': 0.5}
        ]
        for parameters in invalid_parameters_list:
            with self.subTest():
                parameters.update(self.base_form_data)
                form = ALeRCEQueryForm(parameters)
                self.assertFalse(form.is_valid())
                self.assertIn('Only one of either light curve or stamp classification may be used as a filter.',
                              form.errors['__all__'])

    @patch('tom_alerts.brokers.alerce.cache.get')
    @patch('tom_alerts.brokers.alerce.requests.get')
    def test_get_classifiers(self, mock_requests_get, mock_cache_get):
        mock_response = Response()
        mock_response._content = str.encode(json.dumps(alerce_classifiers_response))
        mock_response.status_code = 200
        mock_requests_get.return_value = mock_response

        with self.subTest('Test that cached response avoids request.'):
            mock_cache_get.return_value = alerce_classifiers_response
            classifiers = ALeRCEQueryForm._get_classifiers()
            mock_requests_get.assert_not_called()
            for classifier_group in classifiers:
                self.assertTrue(
                    all(k in classifier_group.keys() for k in ['classifier_name', 'classifier_version', 'classes'])
                )

        with self.subTest('Test that no cached response results in HTTP request.'):
            mock_cache_get.return_value = None
            classifiers = ALeRCEQueryForm._get_classifiers()
            mock_requests_get.assert_called_once()

    @patch('tom_alerts.brokers.alerce.cache.get')
    def test_get_light_curve_classifier_choices(self, mock_cache_get):
        mock_cache_get.return_value = alerce_classifiers_response
        lc_classifiers = ALeRCEQueryForm._get_light_curve_classifier_choices()
        expected_classifiers = [
            (None, ''),
            ('SNIa', 'SNIa - transient'),
            ('QSO', 'QSO - stochastic'),
            ('LPV', 'LPV - periodic')
        ]
        for classifier in expected_classifiers:
            self.assertIn(classifier, lc_classifiers)

    @patch('tom_alerts.brokers.alerce.cache.get')
    def test_get_stamp_classifier_choices(self, mock_cache_get):
        mock_cache_get.return_value = alerce_classifiers_response
        stamp_classifiers = ALeRCEQueryForm._get_stamp_classifier_choices()
        expected_classifiers = {
            (None, ''),
            ('SN', 'SN')
        }
        for classifier in expected_classifiers:
            self.assertIn(classifier, stamp_classifiers)


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
            ({'ra': 10, 'dec': 10, 'radius': None}, []),
            ({'ra': 10, 'dec': 10, 'radius': 10}, [('ra', 10), ('dec', 10), ('radius', 10)])
        ]
        for parameters, expected_list in parameters_list:
            with self.subTest():
                cleaned_coordinate_parameters = self.broker._clean_coordinate_parameters(parameters)
                for expected in expected_list:
                    self.assertIn(expected, cleaned_coordinate_parameters)

    def test_clean_date_parameters(self):
        """Test that _clean_date_parameters results in the correct dict structure."""
        parameters_list = [
            ({'firstmjd__gt': 57000, 'firstmjd__lt': 58000, 'lastmjd__gt': 58000, 'lastmjd__lt': 59000},
             [('firstmjd', 57000), ('firstmjd', 58000), ('lastmjd', 58000), ('lastmjd', 59000)]),
            ({'firstmjd__gt': 57000, 'firstmjd__lt': 58000, 'lastmjd__gt': None, 'lastmjd__lt': None},
             [('firstmjd', 57000), ('firstmjd', 58000)]),
            ({'firstmjd__gt': None, 'firstmjd__lt': None, 'lastmjd__gt': None, 'lastmjd__lt': None}, [])
        ]
        for parameters, expected_list in parameters_list:
            with self.subTest():
                cleaned_date_parameters = self.broker._clean_date_parameters(parameters)
                for expected in expected_list:
                    self.assertIn(expected, cleaned_date_parameters)

    def test_clean_classifier_parameters(self):
        """Test that _clean_filter_parameters results in the correct dict structure."""

        # Test that classifiers are populated correctly
        parameters_list = [
            ({'stamp_classifier': None, 'p_stamp_classifier': None, 'lc_classifier': None, 'p_lc_classifier': None},
             []),
            ({'stamp_classifier': 'SN', 'p_stamp_classifier': None, 'lc_classifier': None, 'p_lc_classifier': None},
             [('classifier', 'stamp_classifier'), ('class', 'SN')]),
            ({'stamp_classifier': 'SN', 'p_stamp_classifier': 0.5, 'lc_classifier': None, 'p_lc_classifier': None},
             [('classifier', 'stamp_classifier'), ('class', 'SN'), ('probability', 0.5)]),
            ({'stamp_classifier': None, 'p_stamp_classifier': None, 'lc_classifier': 'SNIa', 'p_lc_classifier': None},
             [('classifier', 'lc_classifier'), ('class', 'SNIa')]),
            ({'stamp_classifier': None, 'p_stamp_classifier': None, 'lc_classifier': 'SNIa', 'p_lc_classifier': 0.5},
             [('classifier', 'lc_classifier'), ('class', 'SNIa'), ('probability', 0.5)]),
        ]
        for parameters, expected_list in parameters_list:
            with self.subTest():
                for expected in expected_list:
                    cleaned_classifier_parameters = self.broker._clean_classifier_parameters(parameters)
                    self.assertIn(expected, cleaned_classifier_parameters)

    @patch('tom_alerts.brokers.alerce.ALeRCEBroker._clean_classifier_parameters')
    @patch('tom_alerts.brokers.alerce.ALeRCEBroker._clean_date_parameters')
    @patch('tom_alerts.brokers.alerce.ALeRCEBroker._clean_coordinate_parameters')
    def test_clean_parameters(self, mock_coordinate, mock_date, mock_classifier):
        mock_coordinate.return_value = [('ra', 10), ('dec', 10), ('radius', 10)]
        mock_date.return_value = [('firstmjd', 57000), ('firstmjd', 58000), ('lastmjd', 58000), ('lastmjd', 59000)]
        mock_classifier.return_value = [('classifier', 'stamp_classifier'), ('class', 'SN'), ('probability', 0.5)]

        # Ensure that passed in values are used to populate the payload
        parameters = {'page': 2, 'oid': 'testoid', 'ndet': 10, 'ranking': 1, 'order_by': 'oid', 'order_mode': 'ASC'}
        payload = self.broker._clean_parameters(parameters)
        with self.subTest():
            self.assertIn(('page', 2), payload)
            self.assertIn(('page_size', 20), payload)
            for k, v in parameters.items():
                self.assertIn((k, v), payload)
            for expected in mock_coordinate.return_value:
                self.assertIn(expected, payload)
            for expected in mock_date.return_value:
                self.assertIn(expected, payload)
            for expected in mock_classifier.return_value:
                self.assertIn(expected, payload)

        # Ensure that missing values result in default values being used to populate the payload
        payload = self.broker._clean_parameters({})
        with self.subTest():
            self.assertIn(('page', 1), payload)

    @patch('tom_alerts.brokers.alerce.requests.get')
    @patch('tom_alerts.brokers.alerce.ALeRCEBroker._clean_parameters')
    def test_fetch_alerts(self, mock_clean_parameters, mock_requests_get):
        """Test fetch_alerts broker method."""
        first_mock_response_content = create_alerce_query_response(20, page=1)
        first_mock_response = Response()
        first_mock_response._content = str.encode(json.dumps(first_mock_response_content))
        first_mock_response.status_code = 200

        second_mock_response = Response()
        second_mock_response._content = str.encode(json.dumps(create_alerce_query_response(5, page=2)))
        second_mock_response.status_code = 200

        third_mock_response = Response()
        third_mock_response._content = str.encode(json.dumps(create_alerce_query_response(0, page=3)))
        third_mock_response.status_code = 200

        with self.subTest():
            mock_requests_get.side_effect = [first_mock_response, second_mock_response, third_mock_response]
            response = self.broker.fetch_alerts({'max_pages': 5})
            alerts = []
            for alert in response:
                alerts.append(alert)
            self.assertEqual(25, len(alerts))
            self.assertEqual(alerts[0], first_mock_response_content['items'][0])

        with self.subTest():
            mock_requests_get.side_effect = [first_mock_response]
            response = self.broker.fetch_alerts({'max_pages': 1})
            alerts = []
            for alert in response:
                alerts.append(alert)
            self.assertEqual(20, len(alerts))

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
        self.base_form_parameters = {
            'query_name': 'Test ALeRCE',
            'broker': 'ALeRCE',
        }

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

    # These tests fail when running from Github Actions
    # def test_fetch_alerts(self):
    #     form = ALeRCEQueryForm(self.base_form_parameters)
    #     form.is_valid()
    #     query = form.save()

    #     alerts = [alert for alert in self.broker.fetch_alerts(query.parameters)]

    #     self.assertGreaterEqual(len(alerts), 1)
    #     for k in ['oid', 'firstmjd', 'lastmjd', 'class', 'classifier', 'probability', 'meanra', 'meandec']:
    #         self.assertIn(k, alerts[0])

    # def test_fetch_alerts_cone_search(self):
    #     parameters = {'ra': 174.5, 'dec': 5.5, 'radius': 240}
    #     parameters.update(self.base_form_parameters)
    #     form = ALeRCEQueryForm(parameters)
    #     form.is_valid()
    #     query = form.save()

    #     alerts = [alert for alert in self.broker.fetch_alerts(query.parameters)]

    #     self.assertGreaterEqual(len(alerts), 1)
    #     for alert in alerts:
    #         self.assertAlmostEqual(alert['meanra'], 174.5, 0)  # Test that RA is near enough to 174 to be valid
    #         self.assertAlmostEqual(alert['meandec'], 5.5, 0)  # Test that Declination is near enough to 5 to be valid

    # def test_fetch_alerts_classification_search(self):
    #     parameters_list = [
    #         ({'lc_classifier': 'SNIa', 'p_lc_classifier': 0.5},
    #          {'class': 'SNIa', 'classifier': 'lc_classifier', 'probability': 0.5}),
    #         ({'stamp_classifier': 'SN', 'p_stamp_classifier': 0.5},
    #          {'class': 'SN', 'classifier': 'stamp_classifier', 'probability': 0.5})
    #     ]

    #     for parameters, expected in parameters_list:
    #         with self.subTest():
    #             parameters.update(self.base_form_parameters)
    #             form = ALeRCEQueryForm(parameters)
    #             form.is_valid()
    #             query = form.save()

    #             alerts = [alert for alert in self.broker.fetch_alerts(query.parameters)]

    #             self.assertGreaterEqual(len(alerts), 1)
    #             for alert in alerts:
    #                 self.assertEqual(alert['class'], expected['class'])
    #                 self.assertEqual(alert['classifier'], expected['classifier'])
    #                 self.assertGreaterEqual(alert['probability'], expected['probability'])

    # def test_fetch_alerts_time_filters(self):
    #     parameters = {'firstmjd__gt': 59000, 'firstmjd__lt': 59100, 'lastmjd__gt': 59300, 'lastmjd__lt': 59400}
    #     parameters.update(self.base_form_parameters)
    #     form = ALeRCEQueryForm(parameters)
    #     form.is_valid()
    #     query = form.save()

    #     alerts = [alert for alert in self.broker.fetch_alerts(query.parameters)]

    #     self.assertGreaterEqual(len(alerts), 1)
    #     for alert in alerts:
    #         self.assertGreaterEqual(alert['firstmjd'], 59000)
    #         self.assertLessEqual(alert['firstmjd'], 59100)
    #         self.assertGreaterEqual(alert['lastmjd'], 59300)
    #         self.assertLessEqual(alert['lastmjd'], 59400)

    # def test_fetch_alerts_other_filters(self):
    #     parameters = {'ndet': 10}
    #     parameters.update(self.base_form_parameters)
    #     form = ALeRCEQueryForm(parameters)
    #     form.is_valid()
    #     query = form.save()

    #     alerts = [alert for alert in self.broker.fetch_alerts(query.parameters)]

    #     self.assertGreaterEqual(len(alerts), 1)
    #     for alert in alerts:
    #         self.assertGreaterEqual(alert['ndet'], 10)

    # def test_ordering(self):
    #     parameters = {'lc_classifier': 'SNIa'}
    #     parameters.update(self.base_form_parameters)
    #     sorting_parameters = ['oid', 'probability', 'ndet', 'firstmjd', 'lastmjd', 'meanra', 'meandec']
    #     sort_ordering_parameters = ['ASC', 'DESC']

    #     for sorting_parameter in sorting_parameters:
    #         for sort_order in sort_ordering_parameters:
    #             if sorting_parameters != 'ndet' and sort_order != 'ASC':  # This specific combination results in a 500
    #                 with self.subTest():
    #                     parameters.update(self.base_form_parameters)
    #                     parameters.update({'order_by': sorting_parameter, 'order_mode': sort_order})
    #                     form = ALeRCEQueryForm(parameters)
    #                     form.is_valid()
    #                     query = form.save()

    #                     alerts = [alert for alert in self.broker.fetch_alerts(query.parameters)]
    #                     self.assertGreaterEqual(len(alerts), 2)

    #                     last_alert = None
    #                     for alert in alerts:
    #                         if last_alert:
    #                             if sort_order == 'ASC':
    #                                 self.assertGreaterEqual(alert[sorting_parameter], last_alert[sorting_parameter])
    #                             elif sort_order == 'DESC':
    #                                 self.assertLessEqual(alert[sorting_parameter], last_alert[sorting_parameter])

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
