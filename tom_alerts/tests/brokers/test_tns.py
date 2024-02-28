from django.test import TestCase
from requests import Response

from tom_targets.tests.factories import SiderealTargetFactory
from tom_alerts.brokers import tns

tns_classified_target_response = {
    'id_code': 200,
    'id_message': 'OK',
    'data': {
        'received_data': {
            'ra': 41.41608,
            'dec': -20.80996,
            'radius': 1,
            'units': 'arcsec'
        },
        'reply': [
            {
                'objname': '2023xrs',
                'prefix': 'SN',
                'objid': 140367
            }
        ]
    }
}

# class TestClassSN(TestCase):
#     """
#     Class describing unittests for the target planet priority functions
#     """
#     def setUp(self):
#         st1 = SiderealTargetFactory.create()
#         st1.name = 'Gaia23dje'
#         st1.ra = 41.41608
#         st1.dec = -20.80996
#
#         self.params = {
#             'target': st1,
#             'objname' : '2023xrs'
#         }
#
#     def test_transient_response(self):
#         parameters = {
#             'ra': self.params['target'].ra,
#             'dec': self.params['target'].dec,
#             'radius': 1.0,
#             'units': 'arcsec',
#             'days_ago' : None,
#             'min_date' : None,
#         }
#         targets = tns.TNSBroker.fetch_tns_transients(parameters)
#         self.assertEqual(targets['data']['reply'][0]['objname'],
#                          tns_classified_target_response['data']['reply'][0]['objname'])
#         self.assertEqual(targets['data']['reply'][0]['prefix'],
#                          tns_classified_target_response['data']['reply'][0]['prefix']
#                          )
#         self.assertEqual(targets['data']['reply'][0]['objid'],
#                          tns_classified_target_response['data']['reply'][0]['objid']
#                          )
#         # self.assertEqual(targets['reply']['objname'], 'SN Ic-BL')
#
#     def test_object_response(self):
#         parameters = {
#             'objname': self.params['objname']
#         }
#         obj_info = tns.TNSBroker.get_tns_object_info(parameters)
#         # print(obj_info)
#         self.assertEqual(obj_info['data']['reply']['object_type']['name'],
#                          'SN Ic-BL')
#         self.assertEqual(obj_info['data']['reply']['object_type']['id'],
#                          7)

