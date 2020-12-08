from tom_catalogs.harvester import AbstractHarvester

from astroquery.simbad import Simbad


class SimbadHarvester(AbstractHarvester):
    """
    The ``SimbadHarvester`` is the interface to the SIMBAD catalog. At present, it is only queryable by identifier. For
    information regarding identifier format, please see http://simbad.u-strasbg.fr/simbad/sim-fid or
    https://astroquery.readthedocs.io/en/latest/simbad/simbad.html.
    """
    name = 'Simbad'

    def __init__(self, *args, **kwargs):
        self.simbad = Simbad()
        self.simbad.add_votable_fields('pmra', 'pmdec', 'ra(d)', 'dec(d)', 'id', 'parallax', 'distance')

    def query(self, term):
        self.catalog_data = self.simbad.query_object(term)

    def to_target(self):
        target = super().to_target()
        votable_fields = ['RA_d', 'DEC_d', 'PMRA', 'PMDEC', 'ID', 'Distance_distance']
        result = {}
        for key in votable_fields:
            if str(self.catalog_data[key][0]) not in ['--', '']:
                result[key] = self.catalog_data[key][0]
        target.type = 'SIDEREAL'
        target.ra = result.get('RA_d')
        target.dec = result.get('DEC_d')
        target.pm_ra = result.get('PMRA')
        target.pm_dec = result.get('PMDEC')
        target.distance = result.get('Distance_distance')
        result_id = result.get('ID', b'')
        if isinstance(result_id, bytes):  # NOTE: SIMBAD used to return a bytestring, we leave this here in case
            result_id = result_id.decode('UTF-8')
        target.name = result_id.split(',')[0].replace(' ', '')
        return target
