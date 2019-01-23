from tom_catalogs.harvester import AbstractHarvester

import os
import requests
import json
from collections import OrderedDict
from astropy import units as u
from astropy.coordinates import SkyCoord

def get(term):

  api_key = os.environ['TNS_APIKEY']
  url = "https://wis-tns.weizmann.ac.il/api/get"

  try:
    get_url = url + '/object'
    
    # change term to json format
    json_list = [("objname",term)]
    json_file = OrderedDict(json_list)
    
    # construct the list of (key,value) pairs
    get_data = [('api_key',(None, api_key)),
                 ('data',(None,json.dumps(json_file)))]
   
    response = requests.post(get_url, files=get_data)
    response = json.loads(response.text)['data']['reply']
    return response

  except Exception as e:
    return [None,'Error message : \n'+str(e)]

class TNSHarvester(AbstractHarvester):
    name = 'TNS'

    def query(self, term):
        self.catalog_data = get(term)

    def to_target(self):
        target = super().to_target()
        target.type = 'SIDEREAL'
        target.identifier = (self.catalog_data['name_prefix'] +
            self.catalog_data['name'])
        c = SkyCoord('{0} {1}'.format(self.catalog_data['ra'], 
            self.catalog_data['dec']), unit = (u.hourangle, u.deg))
        target.ra, target.dec = c.ra.deg, c.dec.deg
        return target
