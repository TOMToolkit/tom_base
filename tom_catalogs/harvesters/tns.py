import json
import requests

from astropy import units as u
from astropy.coordinates import SkyCoord
from collections import OrderedDict
from django.conf import settings

from tom_alerts.brokers.tns import TNSBroker
from tom_catalogs.harvester import AbstractHarvester
from tom_common.exceptions import ImproperCredentialsException

TNS_URL = 'https://www.wis-tns.org'

try:
    # Check if there is an API key in the HARVESTERS section of settings.py
    TNS_CREDENTIALS = settings.HARVESTERS['TNS']
except (AttributeError, KeyError):
    try:
        # Otherwise, check if there is an API key in the BROKERS section of settings.py
        TNS_CREDENTIALS = settings.BROKERS['TNS']
    except (AttributeError, KeyError):
        TNS_CREDENTIALS = {
            'api_key': ''
        }


def get(term):
    get_url = TNS_URL + '/api/get/object'

    # change term to json format
    json_list = [("objname", term)]
    json_file = OrderedDict(json_list)

    # construct the list of (key,value) pairs
    get_data = [('api_key', (None, TNS_CREDENTIALS['api_key'])),
                ('data', (None, json.dumps(json_file)))]

    try:
        response = requests.post(get_url, files=get_data, headers=TNSBroker.tns_headers())
        response_data = json.loads(response.text)

        if 400 <= response_data.get('id_code') <= 403:
            raise ImproperCredentialsException('TNS: ' + str(response_data.get('id_message')))
    except AttributeError:
        raise ImproperCredentialsException(f"TNS Catalog Search. This requires TNS Broker configuration. "
                                           f"Please see {TNSBroker.help_url} for more information")

    reply = response_data['data']['reply']
    # If TNS succeeds in finding an object, it returns a reply containing the `objname`.
    # If TNS fails to find the object, it returns a reply in the form:
    # {'name': {'110': {'message': 'No results found.', 'message_id': 110}},
    # 'objid': {'110': {'message': 'No results found.', 'message_id': 110}}}
    # In this case, we return None
    if not reply.get('objname', None):
        return None
    return response_data['data']['reply']


class TNSHarvester(AbstractHarvester):
    """
    The ``TNSBroker`` is the interface to the Transient Name Server. For information regarding the TNS, please see
    https://www.wis-tns.org/.
    """

    name = 'TNS'
    help_text = 'Requires object name without prefix.'

    def query(self, term):
        self.catalog_data = get(term)

    def to_target(self):
        target = super().to_target()
        target.type = 'SIDEREAL'
        target.name = (self.catalog_data['name_prefix'] + self.catalog_data['objname'])
        c = SkyCoord('{0} {1}'.format(self.catalog_data['ra'], self.catalog_data['dec']), unit=(u.hourangle, u.deg))
        target.ra, target.dec = c.ra.deg, c.dec.deg
        return target
