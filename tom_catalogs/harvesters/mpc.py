from tom_catalogs.harvester import AbstractHarvester

from astroquery.mpc import MPC


class MPCHarvester(AbstractHarvester):
    """
    The ``MPCHarvester`` is the interface to the Minor Planet Center catalog. For information regarding the Minor Planet
    Center catalog, please see https://minorplanetcenter.net/ or
    https://astroquery.readthedocs.io/en/latest/mpc/mpc.html.
    """

    name = 'MPC'

    def query(self, term):
        self.catalog_data = MPC.query_object('asteroid', name=term)

    def to_target(self):
        target = super().to_target()
        result = self.catalog_data[0]
        target.type = 'NON_SIDEREAL'
        target.name = result['name']
        target.extra_names = [result['designation']] if result['designation'] else []
        target.epoch_of_elements = self.jd_to_mjd(result['epoch_jd'])
        target.mean_anomaly = result['mean_anomaly']
        target.arg_of_perihelion = result['argument_of_perihelion']
        target.eccentricity = result['eccentricity']
        target.lng_asc_node = result['ascending_node']
        target.inclination = result['inclination']
        target.mean_daily_motion = result['mean_daily_motion']
        target.semimajor_axis = result['semimajor_axis']
        return target
