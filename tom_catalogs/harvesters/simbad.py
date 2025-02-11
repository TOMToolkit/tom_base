from tom_catalogs.harvester import AbstractHarvester

from astroquery.simbad import Simbad
from astropy.table import Table


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
        self.catalog_data: Table = self.simbad.query_object(term)
        # astroquery <0.4.10, > 0.4.7 has issues joining the distance field, failing to find any results.
        # This workaround checks if the query result is an ampty table and then tries the query a 2nd time without the
        # distance field.
        if not self.catalog_data:
            self.simbad.reset_votable_fields()
            self.simbad.add_votable_fields('pmra', 'pmdec', 'ra', 'dec', 'main_id', 'parallax')
            self.catalog_data = self.simbad.query_object(term)

    def to_target(self):
        target = super().to_target()
        votable_fields = ['RA', 'DEC', 'PMRA', 'PMDEC', 'MAIN_ID', 'MESDISTANCE.dist', 'MESDISTANCE.unit']
        result = {}
        for key in votable_fields:
            if key.lower() in self.catalog_data.colnames and str(self.catalog_data[key.lower()][0]) not in ['--', '']:
                result[key] = self.catalog_data[key.lower()][0]
        target.type = 'SIDEREAL'
        target.ra = result.get('RA')
        target.dec = result.get('DEC')
        target.pm_ra = result.get('PMRA')
        target.pm_dec = result.get('PMDEC')
        result_id = result.get('MAIN_ID', b'')
        # Convert Distance to pc
        if 'kpc' in result.get('MESDISTANCE.unit', '').lower():
            target.distance = result.get('MESDISTANCE.dist') * 1000
        elif 'mpc' in result.get('MESDISTANCE.unit', '').lower():
            target.distance = result.get('MESDISTANCE.dist') * 1000000
        else:
            target.distance = result.get('MESDISTANCE.dist')
        if isinstance(result_id, bytes):  # NOTE: SIMBAD used to return a bytestring, we leave this here in case
            result_id = result_id.decode('UTF-8')
        target.name = result_id.split(',')[0].replace(' ', '')
        return target
