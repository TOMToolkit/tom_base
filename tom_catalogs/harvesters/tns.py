import json
import requests

from astropy import units as u
from astropy.coordinates import SkyCoord
from collections import OrderedDict
from django.conf import settings

from tom_catalogs.harvester import AbstractHarvester
from tom_common.exceptions import ImproperCredentialsException

TNS_URL = 'https://wis-tns.weizmann.ac.il'

try:
    TNS_CREDENTIALS = settings.ALERT_CREDENTIALS['TNS']
except (AttributeError, KeyError):
    TNS_CREDENTIALS = {
        'api_key': ''
    }


def get(term):
    # url = "https://wis-tns.weizmann.ac.il/api/get"

    get_url = TNS_URL + '/api/get/object'

    # change term to json format
    json_list = [("objname", term)]
    json_file = OrderedDict(json_list)

    # construct the list of (key,value) pairs
    get_data = [('api_key', (None, TNS_CREDENTIALS['api_key'])),
                ('data', (None, json.dumps(json_file)))]

    response = requests.post(get_url, files=get_data)
    response_data = json.loads(response.text)

    if 400 <= response_data.get('id_code') <= 403:
        raise ImproperCredentialsException('TNS: ' + str(response_data.get('id_message')))

    return response_data['data']['reply']


class TNSHarvester(AbstractHarvester):
    """
    The ``TNSBroker`` is the interface to the Transient Name Server. For information regarding the TNS, please see
    https://wis-tns.weizmann.ac.il/.
    """

    name = 'TNS'

    def query(self, term):
        self.catalog_data = get(term)

    def to_target(self):
        target = super().to_target()
        target.type = 'SIDEREAL'
        target.name = (self.catalog_data['name_prefix'] + self.catalog_data['name'])
        c = SkyCoord('{0} {1}'.format(self.catalog_data['ra'], self.catalog_data['dec']), unit=(u.hourangle, u.deg))
        target.ra, target.dec = c.ra.deg, c.dec.deg
        return target
