from requests import Response

from django.utils import timezone
from django.test import TestCase, override_settings
from django.forms import ValidationError
from unittest import mock

from tom_alerts.alerts import get_service_class
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
                    var alerts = [{"name": "Gaia20cpu", "tnsid": "AT2020lto", "obstime": "2020-06-04 17:25:08",
                        "ra": "291.61247", "dec": "13.36801", "alertMag": "20.54", "historicMag": "17.79",
                        "historicStdDev": "0.24", "classification": "CV", "published": "2020-06-06 12:26:16",
                        "comment": "test comment", "per_alert": {"link": "/alerts/alert/Gaia20cpu/", "name":
                        "Gaia20cpu"}, "rvs": false},
                        {"name": "Gaia20bph", "tnsid": "AT2020ftt", "obstime": "2020-04-01 12:52:23",
                        "ra": "34.02266", "dec": "68.65102", "alertMag": "16.21", "historicMag": "18.39",
                        "historicStdDev": "1.22", "classification": "unknown", "published": "2020-04-03 09:47:04",
                        "comment": "candidate CV; several previous outbursts in lightcurve",
                        "per_alert": {"link": "/alerts/alert/Gaia20bph/", "name": "Gaia20bph"}, "rvs": false}];

                    $(document).ready(function() {
                        var index_table = $('#alertsindex').dataTable( {
                            "data": alerts,
                        });
                    });
                </script>
            </html>"""
        self.test_html = self.test_html.replace('\n', '')
        self.alert_list = [
                            {
                                "name": "Gaia20cpu", "tnsid": "AT2020lto", "obstime": "2020-06-04 17:25:08",
                                "ra": "291.61247", "dec": "13.36801", "alertMag": "20.54", "historicMag": "17.79",
                                "historicStdDev": "0.24", "classification": "CV", "published": "2020-06-06 12:26:16",
                                "comment": "test comment", "per_alert": {
                                    "link": "/alerts/alert/Gaia20cpu/", "name": "Gaia20cpu"
                                }, "rvs": 'false'},
                            {
                                "name": "Gaia20bph", "tnsid": "AT2020ftt", "obstime": "2020-04-01 12:52:23",
                                "ra": "34.02266", "dec": "68.65102", "alertMag": "16.21", "historicMag": "18.39",
                                "historicStdDev": "1.22", "classification": "unknown",
                                "published": "2020-04-03 09:47:04",
                                "comment": "candidate CV; several previous outbursts in lightcurve", "per_alert": {
                                    "link": "/alerts/alert/Gaia20bph/", "name": "Gaia20bph"},
                                "rvs": 'false'}
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
        alerts, _ = GaiaBroker().fetch_alerts(search_params)
        self.assertEqual(1, sum(1 for _ in alerts))

        search_params = {'target_name': None, 'cone': '291.61247, 13.36801, 0.002'}
        alerts, _ = GaiaBroker().fetch_alerts(search_params)
        self.assertEqual(1, sum(1 for _ in alerts))

    def test_to_generic_alert(self):
        alert = GaiaBroker().to_generic_alert(self.alert_list[0])
        self.assertEqual(alert.name, self.alert_list[0]['name'])

    @mock.patch('tom_alerts.brokers.gaia.requests.get')
    def test_process_reduced_data_with_alert(self, mock_requests_get):

        mock_photometry_response = Response()
        mock_photometry_response._content = str.encode('''Gaia20bph\n#Date,JD,averagemag.\n
                                    2014-08-01 00:05:24,2456870.504,19.48\n2014-08-01 06:05:38,2456870.754,19.48\n\n''')
        mock_photometry_response.status_code = 200
        mock_requests_get.return_value = mock_photometry_response

        GaiaBroker().process_reduced_data(self.test_target, alert=self.alert_list[0])

        reduced_data = ReducedDatum.objects.filter(target=self.test_target, source_name='Gaia')
        self.assertGreater(reduced_data.count(), 1)
        self.assertEqual(reduced_data.count(), 3)  # one from setUp and two from this test

    @mock.patch('tom_alerts.brokers.gaia.requests.get')
    @mock.patch('tom_alerts.brokers.gaia.GaiaBroker.fetch_alerts')
    def test_process_reduced_data_without_alert(self, mock_fetch_alerts, mock_requests_get):
        mock_fetch_alerts.return_value = iter([self.alert_list[1]])

        mock_photometry_response = Response()
        mock_photometry_response._content = str.encode('''Gaia20bph\n#Date,JD,averagemag.\n
                                    2014-08-01 00:05:24,2456870.504,19.48\n2014-08-01 06:05:38,2456870.754,19.48\n\n''')
        mock_photometry_response.status_code = 200
        mock_requests_get.return_value = mock_photometry_response

        GaiaBroker().process_reduced_data(self.test_target)

        reduced_data = ReducedDatum.objects.filter(target=self.test_target, source_name='Gaia')
        self.assertGreater(reduced_data.count(), 1)
        self.assertEqual(reduced_data.count(), 3)  # one from setUp and two from this test

    def test_get_broker_class(self):
        self.assertEqual(GaiaBroker, get_service_class('Gaia'))

    def test_rewrite_process_reduced_data_with_alert(self):
        """This is just a copy of test_process_reduced_data_with_alert, but with the
        mock.patch decorator replaced with a context manager.

        There are TWO ReducedDatums in the _content mocked below.
        """
        with mock.patch('tom_alerts.brokers.gaia.requests.get') as mock_requests_get:
            mock_photometry_response = Response()
            mock_photometry_response._content = str.encode('''Gaia20bph\n#Date,JD,averagemag.\n
                                    2014-08-01 00:05:24,2456870.504,19.48\n2014-08-01 06:05:38,2456870.754,19.48\n\n''')
            mock_photometry_response.status_code = 200
            mock_requests_get.return_value = mock_photometry_response

            try:
                GaiaBroker().process_reduced_data(self.test_target, alert=self.alert_list[0])
            except ValidationError as e:
                self.fail(f'This test should have created two UNIQUE ReducedDatum objects, but {e}')

        reduced_data = ReducedDatum.objects.filter(target=self.test_target, source_name='Gaia')
        self.assertGreater(reduced_data.count(), 1)
        self.assertEqual(reduced_data.count(), 3)  # one from setUp and two from this test
