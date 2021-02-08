from datetime import datetime, timezone
import json
from requests import Response
from unittest.mock import patch

from astropy.time import Time
from django.test import tag, TestCase
from faker import Faker

from tom_alerts.brokers.alerce import ALeRCEBroker, ALeRCEQueryForm
from tom_targets.models import Target


def create_alerce_alert(lastmjd=None, mean_magpsf_g=None, mean_magpsf_r=None, pclassrf=None, pclassearly=None):
    fake = Faker()

    return {'oid': fake.pystr_format(string_format='ZTF##???????', letters='abcdefghijklmnopqrstuvwxyz'),
            'meanra': fake.pyfloat(min_value=0, max_value=360),
            'meandec': fake.pyfloat(min_value=0, max_value=360),
            'lastmjd': lastmjd if lastmjd else fake.pyfloat(min_value=56000, max_value=59000, right_digits=1),
            'mean_magpsf_g': mean_magpsf_g if mean_magpsf_g else fake.pyfloat(min_value=16, max_value=25),
            'mean_magpsf_r': mean_magpsf_r if mean_magpsf_r else fake.pyfloat(min_value=16, max_value=25),
            'pclassrf': pclassrf if pclassrf else fake.pyfloat(min_value=0, max_value=1),
            'pclassearly': pclassearly if pclassearly else fake.pyfloat(min_value=0, max_value=1)}


def create_alerce_query_response(num_alerts):
    alerts = [create_alerce_alert() for i in range(0, num_alerts)]

    return {
        'total': num_alerts, 'num_pages': 1, 'page': 1,
        'result': {alert['oid']: alert for alert in alerts}
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
            {'ra': 10, 'dec': 10}, {'dec': 10, 'sr': 10}, {'ra': 10, 'sr': 10}
        ]
        for parameters in parameters_list:
            with self.subTest():
                parameters.update(self.base_form_data)
                form = ALeRCEQueryForm(parameters)
                self.assertFalse(form.is_valid())
                self.assertIn('All of RA, Dec, and Search Radius must be included to execute a cone search.',
                              form.non_field_errors())

        # Test that validation passes when all three fields are present
        self.base_form_data.update({'ra': 10, 'dec': 10, 'sr': 10})
        form = ALeRCEQueryForm(self.base_form_data)
        self.assertTrue(form.is_valid())

    def test_time_filters_validation(self):
        """Test validation for time filters."""

        # Test that validation fails when either absolute time filter is paired with relative time filter
        parameters_list = [
            {'mjd__lt': 58000, 'relative_mjd__gt': 168},
            {'mjd__gt': 58000, 'relative_mjd__gt': 168}
        ]
        for parameters in parameters_list:
            with self.subTest():
                parameters.update(self.base_form_data)
                form = ALeRCEQueryForm(parameters)
                self.assertFalse(form.is_valid())
                self.assertIn('Cannot filter by both relative and absolute time.', form.non_field_errors())

        # Test that mjd__lt and mjd__gt fail when mjd__lt is less than mjd__gt
        with self.subTest():
            parameters = {'mjd__lt': 57000, 'mjd__gt': 57001}
            parameters.update(self.base_form_data)
            form = ALeRCEQueryForm(parameters)
            self.assertFalse(form.is_valid())
            self.assertIn('Min date of first detection must be earlier than max date of first detection.',
                          form.non_field_errors())

        # Test that form validation succeeds when relative time fields make sense and absolute time field is used alone.
        parameters_list = [
            {'mjd__gt': 57000, 'mjd__lt': 58000},
            {'relative_mjd__gt': 168}
        ]
        for parameters in parameters_list:
            with self.subTest():
                parameters.update(self.base_form_data)
                form = ALeRCEQueryForm(parameters)
                self.assertTrue(form.is_valid())

        # Test that form validation succeeds when absolute time field is used on its own.
        with self.subTest():
            parameters = {'relative_mjd__gt': 168}
            parameters.update(self.base_form_data)
            form = ALeRCEQueryForm(parameters)
            self.assertTrue(form.is_valid())
            # Test that clean_relative_mjd__gt works as expected
            expected_mjd = Time(datetime.now()).mjd - parameters['relative_mjd__gt']/24
            self.assertAlmostEqual(form.cleaned_data['relative_mjd__gt'], expected_mjd)


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
            ({'ra': 10, 'dec': 10, 'sr': None}, None),
            ({'ra': 10, 'dec': 10, 'sr': 10}, {'ra': 10, 'dec': 10, 'sr': 10})
        ]
        for parameters, expected in parameters_list:
            with self.subTest():
                self.assertEqual(self.broker._clean_coordinate_parameters(parameters), expected)

    def test_clean_date_parameters(self):
        """Test that _clean_date_parameters results in the correct dict structure."""
        parameters_list = [
            ({'mjd__gt': 57000, 'mjd__lt': 58000, 'relative_mjd__gt': None},
             {'firstmjd': {'min': 57000, 'max': 58000}}),
            ({'mjd__gt': 57000, 'mjd__lt': None, 'relative_mjd__gt': None}, {'firstmjd': {'min': 57000}}),
            ({'mjd__gt': None, 'mjd__lt': None, 'relative_mjd__gt': 57000}, {'firstmjd': {'min': 57000}})
        ]
        for parameters, expected in parameters_list:
            with self.subTest():
                self.assertDictEqual(self.broker._clean_date_parameters(parameters), expected)

    def test_clean_filter_parameters(self):
        """Test that _clean_filter_parameters results in the correct dict structure."""
        # Test that number of observations is populated correctly
        parameters_list = [
            ({'nobs__gt': 1, 'nobs__lt': 10}, {'nobs': {'min': 1, 'max': 10}}),
            ({'nobs__gt': 1, 'nobs__lt': None}, {'nobs': {'min': 1}}),
            ({'nobs__gt': None, 'nobs__lt': 10}, {'nobs': {'max': 10}})
        ]
        for parameters, expected in parameters_list:
            with self.subTest():
                parameters.update({k: None for k in ['classrf', 'pclassrf', 'classearly', 'pclassearly']})
                self.assertDictContainsSubset(expected, self.broker._clean_filter_parameters(parameters))

        # Test that classifiers are populated correctly
        parameters_list = [
            ({'classrf': 19, 'pclassrf': 0.7, 'classearly': 10, 'pclassearly': 0.5}),
            ({'classrf': 19, 'pclassrf': 0.7, 'classearly': None, 'pclassearly': None}),
            ({'classrf': None, 'pclassrf': None, 'classearly': 10, 'pclassearly': 0.5})
        ]
        for parameters in parameters_list:
            with self.subTest():
                parameters.update({k: None for k in ['nobs__gt', 'nobs__lt']})
                filters = self.broker._clean_filter_parameters(parameters)
                for key, value in parameters.items():
                    if value is not None:
                        self.assertIn(key, filters)
                    else:
                        self.assertNotIn(key, filters)

    @patch('tom_alerts.brokers.alerce.ALeRCEBroker._clean_filter_parameters')
    @patch('tom_alerts.brokers.alerce.ALeRCEBroker._clean_date_parameters')
    @patch('tom_alerts.brokers.alerce.ALeRCEBroker._clean_coordinate_parameters')
    def test_clean_parameters(self, mock_coordinate, mock_date, mock_filter):
        mock_coordinate.return_value = {'ra': 10, 'dec': 10, 'sr': 10}
        mock_date.return_value = {'firstmjd': {'min': 58000}}
        mock_filter.return_value = {'nobs__gt': 1}

        # Ensure that passed in values are used to populate the payload
        parameters = {'page': 2, 'records': 25, 'sort_by': 'lastmjd', 'total': 30}
        payload = self.broker._clean_parameters(parameters)
        with self.subTest():
            self.assertEqual(payload['page'], parameters['page'])
            self.assertEqual(payload['records_per_pages'], parameters['records'])
            self.assertEqual(payload['sortBy'], parameters['sort_by'])
            self.assertEqual(payload['total'], parameters['total'])
            self.assertIn('firstmjd', payload['query_parameters']['dates'])
            self.assertIn('nobs__gt', payload['query_parameters']['filters'])
            self.assertIn('coordinates', payload['query_parameters'])

        # Ensure that missing values result in default values being used to populate the payload
        mock_coordinate.return_value = None
        payload = self.broker._clean_parameters({})
        with self.subTest():
            self.assertEqual(payload['page'], 1)
            self.assertEqual(payload['records_per_pages'], 20)
            self.assertEqual(payload['sortBy'], 'nobs')
            self.assertNotIn('total', payload)
            self.assertNotIn('coordinates', payload['query_parameters'])

    @patch('tom_alerts.brokers.alerce.requests.post')
    @patch('tom_alerts.brokers.alerce.ALeRCEBroker._clean_parameters')
    def test_fetch_alerts(self, mock_clean_parameters, mock_requests_post):
        """Test fetch_alerts broker method."""
        mock_response = Response()
        mock_response_content = create_alerce_query_response(25)
        mock_response._content = str.encode(json.dumps(mock_response_content))
        mock_response.status_code = 200
        mock_requests_post.return_value = mock_response

        response = self.broker.fetch_alerts({})
        alerts = []
        for alert in response:
            alerts.append(alert)
            self.assertDictEqual(alert, mock_response_content['result'][alert['oid']])
        self.assertEqual(25, len(alerts))

    @patch('tom_alerts.brokers.alerce.requests.post')
    def test_fetch_alert(self, mock_requests_post):
        """Test fetch_alert broker method."""
        mock_response = Response()
        mock_response_content = create_alerce_query_response(1)
        mock_response._content = str.encode(json.dumps(mock_response_content))
        mock_response.status_code = 200
        mock_requests_post.return_value = mock_response

        alert = self.broker.fetch_alert(list(mock_response_content['result'])[0])
        self.assertDictEqual(list(mock_response_content['result'].items())[0][1], alert)

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

        # Test that the magnitude is selected correctly
        mock_alert = create_alerce_alert(mean_magpsf_g=20, mean_magpsf_r=18)
        self.assertEqual(mock_alert['mean_magpsf_r'], self.broker.to_generic_alert(mock_alert).mag)

        mock_alert = create_alerce_alert(mean_magpsf_g=18, mean_magpsf_r=20)
        self.assertEqual(mock_alert['mean_magpsf_g'], self.broker.to_generic_alert(mock_alert).mag)

        mock_alert = create_alerce_alert(mean_magpsf_r=18)
        mock_alert['mean_magpsf_g'] = None
        self.assertEqual(mock_alert['mean_magpsf_r'], self.broker.to_generic_alert(mock_alert).mag)

        mock_alert = create_alerce_alert(mean_magpsf_g=18, mean_magpsf_r=20)
        mock_alert['mean_magpsf_r'] = None
        self.assertEqual(mock_alert['mean_magpsf_g'], self.broker.to_generic_alert(mock_alert).mag)

        # Test that the classification is selected correctly
        mock_alert = create_alerce_alert()
        self.assertEqual(mock_alert['pclassrf'], self.broker.to_generic_alert(mock_alert).score)

        mock_alert = create_alerce_alert()
        mock_alert['pclassrf'] = None
        self.assertEqual(mock_alert['pclassearly'], self.broker.to_generic_alert(mock_alert).score)

        mock_alert = create_alerce_alert()
        mock_alert['pclassrf'] = None
        mock_alert['pclassearly'] = None
        self.assertEqual(None, self.broker.to_generic_alert(mock_alert).score)


@tag('canary')
class TestALeRCEModuleCanary(TestCase):
    def setUp(self):
        self.broker = ALeRCEBroker()

    @patch('tom_alerts.brokers.alerce.cache.get')
    def test_get_classifiers(self, mock_cache_get):
        mock_cache_get.return_value = None  # Ensure cache is not used

        classifiers = ALeRCEQueryForm._get_classifiers()
        self.assertIn('early', classifiers.keys())
        self.assertIn('late', classifiers.keys())
        for classifier in classifiers['early'] + classifiers['late']:
            self.assertIn('name', classifier.keys())
            self.assertIn('id', classifier.keys())

    def test_fetch_alerts(self):
        form = ALeRCEQueryForm({'query_name': 'Test', 'broker': 'ALeRCE', 'nobs__gt': 1, 'classearly': 19,
                                'pclassearly': 0.7, 'mjd__gt': 59148.78219219812})
        form.is_valid()
        query = form.save()

        alerts = [alert for alert in self.broker.fetch_alerts(query.parameters)]

        self.assertGreaterEqual(len(alerts), 6)
        for k in ['oid', 'lastmjd', 'mean_magpsf_r', 'mean_magpsf_g', 'pclassrf', 'pclassearly', 'meanra', 'meandec']:
            self.assertIn(k, alerts[0])

    def test_fetch_alert(self):
        alert = self.broker.fetch_alert('ZTF20acnsdjd')

        self.assertDictContainsSubset({
            'oid': 'ZTF20acnsdjd',
            'first_magpsf_g': 17.3446006774902,
            'first_magpsf_r': 17.0198993682861,
            'firstmjd': 59149.1119328998,
        }, alert)
