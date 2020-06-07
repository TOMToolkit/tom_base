from requests import Response

from django.test import TestCase, override_settings
from django.forms import ValidationError
from unittest import mock

from tom_alerts.brokers.gaia import GaiaQueryForm

@override_settings(TOM_ALERT_CLASSES=['tom_alerts.brokers.gaia.GaiaBroker'])
class TestGaiaQueryForm(TestCase):
    def setUp(self):
        self.base_form_params = {'query_name': 'Test Query', 'broker': 'Gaia'}

    def test_with_required_params(self):
        self.base_form_params['target_name'] = 'Test Target'
        form = GaiaQueryForm(self.base_form_params)
        self.assertTrue(form.is_valid())

    def test_no_query_name(self):
        self.base_form_params['target_name'] = 'Test Target'
        self.base_form_params.pop('query_name')
        form = GaiaQueryForm(self.base_form_params)
        self.assertFalse(form.is_valid())
        self.assertIn('This field is required.', form.errors.get('query_name'))

    def test_no_target_name_or_cone(self):
        form = GaiaQueryForm(self.base_form_params)
        self.assertFalse(form.is_valid())
        with self.assertRaises(ValidationError):
            form.clean()
        self.assertIn('Please enter either a target name or cone search parameters.', form.errors.get('__all__'))

    def test_both_target_name_and_cone(self):
        self.base_form_params['target_name'] = 'Test Target'
        self.base_form_params['cone'] = '10,20,3'
        form = GaiaQueryForm(self.base_form_params)
        self.assertFalse(form.is_valid())
        with self.assertRaises(ValidationError):
            form.clean()
        self.assertIn('Please only enter one of target name or cone search parameters.', form.errors.get('__all__'))

    def test_cone(self):
        self.base_form_params['cone'] = '10,20,3'
        form = GaiaQueryForm(self.base_form_params)
        self.assertTrue(form.is_valid())

    def test_cone_invalid_format(self):
        self.base_form_params['cone'] = '10'
        form = GaiaQueryForm(self.base_form_params)
        self.assertFalse(form.is_valid())
        with self.assertRaises(ValidationError):
            form.clean()
        self.assertIn('Cone search parameters must be in the format \'RA,Dec,Radius\'.', form.errors.get('cone'))


@override_settings(TOM_ALERT_CLASSES=['tom_alerts.brokers.gaia.GaiaBroker'])
class TestGaiaBroker(TestCase):
    def setUp(self):
        self.test_html = """
            <html>
                <script charset="utf-8" type="text/javascript">
	                var alerts = [{"name": "Gaia20cpu", "tnsid": "AT2020lto", "obstime": "2020-06-04 17:25:08", "ra": "291.61247", 
				        "dec": "13.36801", "alertMag": "20.54", "historicMag": "17.79", "historicStdDev": "0.24", 
				        "classification": "CV", "published": "2020-06-06 12:26:16", "comment": "test comment", 
				        "per_alert": {"link": "/alerts/alert/Gaia20cpu/", "name": "Gaia20cpu"}, "rvs": false}];
	
	                $(document).ready(function() {
		                var index_table = $('#alertsindex').dataTable( {                                          
			                "data": alerts, 
		                });
	                });
                </script>
            </html>"""

    @mock.patch('tom_alerts.brokers.mars.requests.get')
    def test_fetch_alerts(self, mock_requests_get):
        mock_response = Response()
        mock_response._content = self.test_html
        mock_response.status_code = 200
        mock_requests_get.return_value = mock_response

        # (\[{)(.*?)(}\])