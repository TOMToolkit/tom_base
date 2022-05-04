from datetime import datetime
from itertools import islice
import json
from requests import Response

from django.utils import timezone
from django.test import override_settings, tag, TestCase
from unittest import mock

from tom_alerts.brokers.mars import MARSBroker
from tom_alerts.alerts import get_service_class
from tom_targets.models import Target
from tom_dataproducts.models import ReducedDatum

alert1 = {
    'candid': 617122521615015023,
    'candidate': {
       'b': 0.70548695469711,
       'dec': -10.5296018,
       'jd': 2458371.6225231,
       'l': 20.7124513780029,
       'magpsf': 16.321626663208,
       'ra': 276.5843017,
       'rb': 0.990000009536743,
       'wall_time': 'Mon, 10 Sep 2018 02:56:25 GMT',
    },
    'lco_id': 11296149,
    'objectId': 'ZTF18abbkloa',
}


@override_settings(TOM_ALERT_CLASSES=['tom_alerts.brokers.mars.MARSBroker'])
class TestMARSBrokerClass(TestCase):
    """ Test the functionality of the MARSBroker, we modify the django settings to make sure
    it is the only installed broker.
    """
    def setUp(self):
        self.test_target = Target.objects.create(name='ZTF18aberpsh')
        ReducedDatum.objects.create(
            source_name='MARS',
            source_location=11053318,
            target=self.test_target,
            data_type='photometry',
            timestamp=timezone.now(),
            value=12
        )
        alert2 = alert1.copy()
        alert2['lco_id'] = 11053318
        alert2['objectId'] = 'ZTF18aberpsh'
        self.test_data = [alert1, alert2]

    def test_get_broker_class(self):
        self.assertEqual(MARSBroker, get_service_class('MARS'))

    def test_get_invalid_broker(self):
        with self.assertRaises(ImportError):
            get_service_class('LASAIR')

    @mock.patch('tom_alerts.brokers.mars.requests.get')
    def test_fetch_alerts(self, mock_requests_get):
        mock_return_data = {
            "has_next": "false",
            "has_prev": "false",
            "pages": 1,
            "results": [self.test_data[1]]
        }
        mock_response = Response()
        mock_response._content = str.encode(json.dumps(mock_return_data))
        mock_response.status_code = 200
        mock_requests_get.return_value = mock_response

        alerts = MARSBroker().fetch_alerts({'objectId': 'ZTF18aberpsh'})
        self.assertEqual(self.test_data[1]['objectId'], list(alerts)[0]['objectId'])

    def test_process_reduced_data_with_alert(self):
        test_alert = self.test_data[1]
        test_alert['prv_candidate'] = [
            {
                'candidate': {
                    'jd': 2458372.6225231,
                    'magpsf': 13,
                    'sigmapsf': 0.5,
                    'fid': 1
                }
            }
        ]

        MARSBroker().process_reduced_data(self.test_target, alert=test_alert)
        reduced_data = ReducedDatum.objects.filter(target=self.test_target, source_name='MARS')
        self.assertEqual(reduced_data.count(), 2)

    @mock.patch('tom_alerts.brokers.mars.MARSBroker.fetch_alert')
    def test_process_reduced_data_no_alert(self, mock_fetch_alert):
        self.test_data = self.test_data[1]
        self.test_data['prv_candidate'] = [
            {
                'candidate': {
                    'jd': 2458372.6225231,
                    'magpsf': 13,
                    'sigmapsf': 0.5,
                    'fid': 1
                }
            }
        ]
        mock_fetch_alert.return_value = self.test_data

        MARSBroker().process_reduced_data(self.test_target)
        reduced_data = ReducedDatum.objects.filter(target=self.test_target, source_name='MARS')
        self.assertEqual(reduced_data.count(), 2)

    def test_to_target(self):
        test_alert = self.test_data[0]

        created_target = MARSBroker().to_target(test_alert)
        self.assertEqual(created_target.name, 'ZTF18abbkloa')

    def test_to_generic_alert(self):
        test_alert = self.test_data[1]

        created_alert = MARSBroker().to_generic_alert(test_alert)
        self.assertEqual(created_alert.name, 'ZTF18aberpsh')


@tag('canary')
class TestMARSModuleCanary(TestCase):
    def setUp(self):
        self.broker = MARSBroker()
        self.expected_keys = ['avro', 'candid', 'candidate', 'lco_id', 'objectId', 'publisher']
        self.expected_candidate_keys = ['aimage', 'aimagerat', 'b', 'bimage', 'bimagerat', 'candid', 'chinr', 'chipsf',
                                        'classtar', 'clrcoeff', 'clrcounc', 'clrmed', 'clrrms', 'dec', 'decnr',
                                        'deltamaglatest', 'deltamagref', 'diffmaglim', 'distnr', 'distpsnr1',
                                        'distpsnr2', 'distpsnr3', 'drb', 'drbversion', 'dsdiff', 'dsnrms', 'elong',
                                        'exptime', 'fid', 'field', 'filter', 'fwhm', 'isdiffpos', 'jd', 'jdendhist',
                                        'jdendref', 'jdstarthist', 'jdstartref', 'l', 'magap', 'magapbig', 'magdiff',
                                        'magfromlim', 'maggaia', 'maggaiabright', 'magnr', 'magpsf', 'magzpsci',
                                        'magzpscirms', 'magzpsciunc', 'mindtoedge', 'nbad', 'ncovhist', 'ndethist',
                                        'neargaia', 'neargaiabright', 'nframesref', 'nid', 'nmatches', 'nmtchps',
                                        'nneg', 'objectidps1', 'objectidps2', 'objectidps3', 'pdiffimfilename', 'pid',
                                        'programid', 'programpi', 'ra', 'ranr', 'rb', 'rbversion', 'rcid', 'rfid',
                                        'scorr', 'seeratio', 'sgmag1', 'sgmag2', 'sgmag3', 'sgscore1', 'sgscore2',
                                        'sgscore3', 'sharpnr', 'sigmagap', 'sigmagapbig', 'sigmagnr', 'sigmapsf',
                                        'simag1', 'simag2', 'simag3', 'sky', 'srmag1', 'srmag2', 'srmag3', 'ssdistnr',
                                        'ssmagnr', 'ssnamenr', 'ssnrms', 'sumrat', 'szmag1', 'szmag2', 'szmag3',
                                        'tblid', 'tooflag', 'wall_time', 'xpos', 'ypos', 'zpclrcov', 'zpmed']

    def test_fetch_alerts(self):
        response = self.broker.fetch_alerts({'time__gt': '2018-06-01', 'time__lt': '2018-06-30'})

        alerts = []
        for alert in islice(response, 10):
            alerts.append(alert)
        self.assertEqual(len(alerts), 10)

        for key in self.expected_keys:
            self.assertTrue(key in alerts[0].keys())
        for key in self.expected_candidate_keys:
            self.assertTrue(key in alerts[0]['candidate'].keys())

    def test_fetch_alert(self):
        alert = self.broker.fetch_alert(1065519)

        for key in self.expected_keys:
            self.assertTrue(key in alert.keys())
        for key in self.expected_candidate_keys:
            self.assertTrue(key in alert['candidate'].keys())

    def test_process_reduced_data(self):
        alert = self.broker.fetch_alert(1065519)
        t = Target.objects.create(name='test target', ra=1, dec=2)
        self.broker.process_reduced_data(t, alert=alert)
        self.assertGreaterEqual(ReducedDatum.objects.filter(target=t, timestamp__lte=datetime(2020, 11, 3)).count(),
                                526)
