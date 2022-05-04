from astroquery.ned import Ned
from astroquery.exceptions import RemoteServiceError

from tom_catalogs.harvester import AbstractHarvester


class NEDHarvester(AbstractHarvester):
    """
    The ``NEDHarvester`` is the interface to the NASA/IPAC Extragalactic Database. For information regarding the NED
    catalog, please see https://ned.ipac.caltech.edu/ or https://astroquery.readthedocs.io/en/latest/ned/ned.html.
    """

    name = 'NED'

    def query(self, term):
        try:
            self.catalog_data = Ned.query_object(term)
        except RemoteServiceError:
            self.catalog_data = {}

    def to_target(self):
        target = super().to_target()
        target.type = 'SIDEREAL'
        target.name = self.catalog_data['Object Name'][0]
        target.ra = self.catalog_data['RA'][0]
        target.dec = self.catalog_data['DEC'][0]
        return target
