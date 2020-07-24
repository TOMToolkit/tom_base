from requests import Response

from django.utils import timezone
from django.test import TestCase, override_settings
from django.forms import ValidationError
from unittest import mock

from tom_alerts.brokers.gaia import GaiaQueryForm
from tom_alerts.brokers.gaia import GaiaBroker
from tom_targets.models import Target
from tom_dataproducts.models import ReducedDatum

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
				        "per_alert": {"link": "/alerts/alert/Gaia20cpu/", "name": "Gaia20cpu"}, "rvs": false},
                        {"name": "Gaia16aau", "tnsid": "AT2016dbu", "obstime": "2016-01-25 18:25:07", "ra": "12.54460",
                        "dec": "-69.73271", "alertMag": "15.13", "historicMag": "", "historicStdDev": "", "classification": "RCrB",
                        "published": "2016-01-30 13:46:16", "comment": "5mag change in 400days in Carbon Star [MH95]580,
                        but spectrum rather blue. Candidate RCrB ?", "per_alert": {"link": "/alerts/alert/Gaia16aau/",
                        "name": "Gaia16aau"}, "rvs": false}, {"name": "Gaia16aat", "tnsid": "AT2016dbx", "obstime": "2016-01-22 03:39:40",
                        "ra": "246.20861", "dec": "65.68363", "alertMag": "19.36", "historicMag": "", "historicStdDev": "",
                        "classification": "unknown", "published": "2016-01-30 13:22:05", "comment":
                        "long-term rise on a blue star seen in DSS2 and Galex", "per_alert": {"link": "/alerts/alert/Gaia16aat/",
                        "name": "Gaia16aat"}, "rvs": false}, {"name": "Gaia20bph", "tnsid": "AT2020ftt", "obstime": "2020-04-01 12:52:23",
                        "ra": "34.02266", "dec": "68.65102", "alertMag": "16.21", "historicMag": "18.39", "historicStdDev": "1.22",
                        "classification": "unknown", "published": "2020-04-03 09:47:04",
                        "comment": "candidate CV; several previous outbursts in lightcurve",
                        "per_alert": {"link": "/alerts/alert/Gaia20bph/", "name": "Gaia20bph"}, "rvs": false}];

	                $(document).ready(function() {
		                var index_table = $('#alertsindex').dataTable( {
			                "data": alerts,
		                });
	                });
                </script>
            </html>"""
        self.test_html = self.test_html.replace('\n','')
        self.alert_list = [ {"name": "Gaia20cpu", "tnsid": "AT2020lto", "obstime": "2020-06-04 17:25:08", "ra": "291.61247",
            "dec": "13.36801", "alertMag": "20.54", "historicMag": "17.79", "historicStdDev": "0.24",
            "classification": "CV", "published": "2020-06-06 12:26:16", "comment": "test comment",
            "per_alert": {"link": "/alerts/alert/Gaia20cpu/", "name": "Gaia20cpu"}, "rvs": 'false'},
                        {"name": "Gaia16aau", "tnsid": "AT2016dbu", "obstime": "2016-01-25 18:25:07", "ra": "12.54460",
            "dec": "-69.73271", "alertMag": "15.13", "historicMag": "", "historicStdDev": "", "classification": "RCrB",
            "published": "2016-01-30 13:46:16", "comment": "5mag change in 400days in Carbon Star [MH95]580, but spectrum rather blue. Candidate RCrB ?",
            "per_alert": {"link": "/alerts/alert/Gaia16aau/","name": "Gaia16aau"}, "rvs": 'false'},
                        {"name": "Gaia16aat", "tnsid": "AT2016dbx", "obstime": "2016-01-22 03:39:40",
            "ra": "246.20861", "dec": "65.68363", "alertMag": "19.36", "historicMag": "", "historicStdDev": "",
            "classification": "unknown", "published": "2016-01-30 13:22:05", "comment":
            "long-term rise on a blue star seen in DSS2 and Galex", "per_alert": {"link": "/alerts/alert/Gaia16aat/",
            "name": "Gaia16aat"}, "rvs": 'false'},
                        {"name": "Gaia20bph", "tnsid": "AT2020ftt", "obstime": "2020-04-01 12:52:23",
            "ra": "34.02266", "dec": "68.65102", "alertMag": "16.21", "historicMag": "18.39", "historicStdDev": "1.22",
            "classification": "unknown", "published": "2020-04-03 09:47:04",
            "comment": "candidate CV; several previous outbursts in lightcurve",
            "per_alert": {"link": "/alerts/alert/Gaia20bph/", "name": "Gaia20bph"}, "rvs": 'false'}
                        ]
        self.test_target = Target.objects.create(name=self.alert_list[0]['name'])
        ReducedDatum.objects.create(
            source_name='Gaia',
            source_location=111111,
            target=self.test_target,
            data_type='photometry',
            timestamp=timezone.now(),
            value=12345.6789
        )

    @mock.patch('tom_alerts.brokers.gaia.requests.get')
    def test_fetch_alerts(self, mock_requests_get):
        mock_response = Response()
        mock_response._content = self.test_html
        mock_response.status_code = 200
        mock_requests_get.return_value = mock_response

        search_params = {'target_name': 'Gaia20bph', 'cone': None, }
        alerts = GaiaBroker().fetch_alerts(search_params)
        self.assertEqual(1, sum(1 for _ in alerts))

        search_params = {'target_name': None, 'cone': '291.61247, 13.36801, 0.002' }
        alerts = GaiaBroker().fetch_alerts(search_params)
        self.assertEqual(1, sum(1 for _ in alerts))

    def test_to_generic_alert(self):
        alert = GaiaBroker().to_generic_alert(self.alert_list[0])
        self.assertEqual(alert.name, self.alert_list[0]['name'])

    @mock.patch('tom_alerts.brokers.gaia.GaiaBroker.fetch_alert')
    def test_process_reduced_data_with_alert(self, mock_fetch_alert):
        mock_response = Response()
        mock_response._content = self.test_html
        mock_response.status_code = 200
        mock_fetch_alert.return_value = mock_response

        GaiaBroker().process_reduced_data(self.test_target, alert=self.alert_list[0])

        reduced_data = ReducedDatum.objects.filter(target=self.test_target, source_name='Gaia')
        self.assertGreater(reduced_data.count(), 1)

    def test_process_reduced_data_without_alert(self):
        GaiaBroker().process_reduced_data(self.test_target)

        reduced_data = ReducedDatum.objects.filter(target=self.test_target, source_name='Gaia')
        self.assertGreater(reduced_data.count(), 1)
