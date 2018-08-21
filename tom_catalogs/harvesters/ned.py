from astroquery.ned import Ned
from astroquery.exceptions import RemoteServiceError

from tom_catalogs.harvester import AbstractHarvester


class NEDHarvester(AbstractHarvester):
    name = 'NED'

    def query(self, term):
        try:
            self.catalog_data = Ned.query_object(term)
        except RemoteServiceError:
            self.catalog_data = {}

    def to_target(self):
        target = super().to_target()
        target.type = 'SIDEREAL'
        target.identifier = self.catalog_data['Object Name'][0]
        target.ra = self.catalog_data['RA(deg)'][0]
        target.dec = self.catalog_data['DEC(deg)'][0]
        return target
