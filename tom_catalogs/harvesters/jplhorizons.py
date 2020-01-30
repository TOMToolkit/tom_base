from astroquery.jplhorizons import Horizons

from tom_catalogs.harvester import AbstractHarvester


class JPLHorizonsHarvester(AbstractHarvester):
    """
    The ``JPLHorizonsHarvester`` is the interface to the JPL Horizons catalog. For information regarding the JPL
    Horizons catalog, please see https://ssd.jpl.nasa.gov/?horizons or
    https://astroquery.readthedocs.io/en/latest/jplhorizons/jplhorizons.html.
    """

    name = 'JPL Horizons'

    def query(self, term, location=None, start=None, end=None, step=None):
        if all((start, end, step)):
            epochs = {'start': start, 'end': end, 'step': step}
        else:
            epochs = None
        try:
            obj = Horizons(id=term, location=location, epochs=epochs)
            self.catalog_data = obj.elements()
        except (ValueError, IOError):
            self.catalog_data = {}

    def to_target(self):
        target = super().to_target()
        target.type = 'NON_SIDEREAL'
        target.name = str(self.catalog_data['targetname'][0])
        target.mean_anomaly = self.catalog_data['M'][0]  # mean anomaly in JPL astroquery column names
        target.arg_of_perihelion = self.catalog_data['w'][0]  # argument of the perifocus in JPL astroquery column names
        target.lng_asc_node = self.catalog_data['Omega'][0]  # logintude of asc. node in JPL astroquery column names
        target.inclination = self.catalog_data['incl'][0]  # inclination in JPL astroquery column names
        target.mean_daily_motion = self.catalog_data['n'][0]  # mean motion in JPL astroquery column names
        target.semimajor_axis = self.catalog_data['a'][0]  # semi-major axis in JPL astroquery column names
        target.eccentricity = self.catalog_data['e'][0]  # eccentricity in JPL astroquery column names
        target.epoch = self.catalog_data['datetime_jd'][0]  # epoch Julian Date in JPL astroquery column names
        target.epoch_of_perihelion = self.catalog_data['Tp_jd'][0]  # time of periapsis in JPL astroquery column names
        target.perihdist = self.catalog_data['q'][0]  # periapsis distance in JPL astroquery column names
        # undocumented in JPL astroquery column names -- presuming P is the orbital period in JPL
        target.ephemeris_period = self.catalog_data['P'][0]
        return target
