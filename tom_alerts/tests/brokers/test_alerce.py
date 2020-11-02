from datetime import datetime

from astropy.time import Time
from django.test import tag, TestCase

from tom_alerts.brokers.alerce import ALeRCEBroker, ALeRCEQueryForm


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
                print(parameters)
                form = ALeRCEQueryForm(parameters)
                print(form.errors)
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

    # def test_clean_parameters(self):
    #     form = ALeRCEQueryForm(self.base_form_data)
    #     form.is_valid()
    #     print(form.cleaned_data)
    #     query = form.save()
    #     print(query.parameters_as_dict)
    #     cleaned_params = self.broker._clean_parameters(query.parameters_as_dict)
    #     payload = self.broker._fetch_alerts_payload(query.parameters_as_dict)
    #     print(cleaned_params)
    #     print(payload)

    def test_fetch_alerts(self):
        pass

    def test_fetch_alert(self):
        pass

    def test_to_target(self, alert):
        pass

    def test_to_generic_alert(self, alert):
        pass


@tag('canary')
class TestALeRCEModuleCanary(TestCase):
    def setUp(self):
        pass

    def test_early_classifier_choices(self):
        pass

    def test_late_classifier_choices(self):
        pass

    def test_fetch_alerts(self):
        pass

    def test_fetch_alert(self):
        pass

    def test_process_reduced_data(self):
        pass
