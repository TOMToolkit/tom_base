from tom_catalogs.harvester import AbstractHarvester
from tom_targets.models import Target
from astroquery.simbad import Simbad


def register(registrar):
    return SimbadHarvester.register(registrar)


class MissingDataException(Exception):
    pass


class SimbadHarvester(AbstractHarvester):
    name = 'Simbad'

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.simbad = Simbad()
        self.simbad.add_votable_fields('pmra', 'pmdec', 'ra(d)', 'dec(d)', 'id', 'parallax', 'distance')

    @classmethod
    def register(clz, registrar):
        registrar.register(clz, clz.name)

    def query(self, term):
        super().query(term)
        self.catalog_data = self.simbad.query_object(term)

    def to_target(self):
        votable_fields = ['RA_d', 'DEC_d', 'PMRA', 'PMDEC', 'ID', 'Distance_distance']
        if self.catalog_data:
            result = {}
            for key in votable_fields:
                if str(self.catalog_data[key][0]) not in ['--', '']:
                    result[key] = self.catalog_data[key][0]
            return Target(
                ra=result.get('RA_d'), dec=result.get('DEC_d'), pm_ra=result.get('PMRA'), pm_dec=result.get('PMDEC'),
                distance=result.get('Distance_distance'), identifier=str(result.get('ID', '')).split(',')[0]
            )
        else:
            raise MissingDataException('No catalog data. Did you call query()?')
