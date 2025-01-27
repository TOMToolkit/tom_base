from tom_catalogs.harvester import AbstractHarvester

from astroquery.simbad import Simbad
from astroquery.exceptions import TableParseError


class SimbadHarvester(AbstractHarvester):
    """
    The ``SimbadHarvester`` is the interface to the SIMBAD catalog. At present, it is only queryable by identifier. For
    information regarding identifier format, please see http://simbad.u-strasbg.fr/simbad/sim-fid or
    https://astroquery.readthedocs.io/en/latest/simbad/simbad.html.
    """
    name = 'Simbad'

    def __init__(self, *args, **kwargs):
        self.simbad = Simbad()
        self.simbad.add_votable_fields('pmra', 'pmdec', 'ra', 'dec', 'main_id', 'parallax', 'distance')

    def query(self, term):
        try:
            self.catalog_data = self.simbad.query_object(term)
        except TableParseError:  # SIMBAD will raise a TableParseError if a result is not found
            self.catalog_data = None  # The CatalogQueryView will display a proper error if catalog_data is None

    def to_target(self):
        target = super().to_target()
        votable_fields = ['RA', 'DEC', 'PMRA', 'PMDEC', 'MAIN_ID', 'MESDISTANCE.dist', 'MESDISTANCE.unit']
        result = {}
        for key in votable_fields:
            if str(self.catalog_data[key.lower()][0]) not in ['--', '']:
                result[key] = self.catalog_data[key.lower()][0]
        target.type = 'SIDEREAL'
        target.ra = result.get('RA')
        target.dec = result.get('DEC')
        target.pm_ra = result.get('PMRA')
        target.pm_dec = result.get('PMDEC')
        result_id = result.get('MAIN_ID', b'')
        # Convert Distance to pc
        if 'kpc' in result.get('MESDISTANCE.unit').lower():
            target.distance = result.get('MESDISTANCE.dist') * 1000
        elif 'mpc' in result.get('MESDISTANCE.unit').lower():
            target.distance = result.get('MESDISTANCE.dist') * 1000000
        else:
            target.distance = result.get('MESDISTANCE.dist')
        if isinstance(result_id, bytes):  # NOTE: SIMBAD used to return a bytestring, we leave this here in case
            result_id = result_id.decode('UTF-8')
        target.name = result_id.split(',')[0].replace(' ', '')
        return target
