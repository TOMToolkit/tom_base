from astroquery.jplhorizons import Horizons

from tom_catalogs.harvester import AbstractHarvester


class JPLHorizonsHarvester(AbstractHarvester):
    """
    The ``JPLHorizonsHarvester`` is the interface to the JPL Horizons catalog. For information regarding the JPL
    Horizons catalog, please see https://ssd.jpl.nasa.gov/?horizons or
    https://astroquery.readthedocs.io/en/latest/jplhorizons/jplhorizons.html.
    """

    name = 'JPL Horizons'
    help_text = 'Query the JPL Horizons Minor Body catalog.'

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
        target.scheme = 'MPC_MINOR_PLANET'
        target.name = str(self.catalog_data['targetname'][0])
        target.mean_anomaly = self.catalog_data['M'][0]  # mean anomaly in JPL astroquery column names
        target.arg_of_perihelion = self.catalog_data['w'][0]  # argument of the perifocus in JPL
        target.lng_asc_node = self.catalog_data['Omega'][0]  # longitude of asc. node in JPL
        target.inclination = self.catalog_data['incl'][0]  # inclination in JPL
        target.mean_daily_motion = self.catalog_data['n'][0]  # mean motion in JPL
        target.semimajor_axis = self.catalog_data['a'][0]  # semi-major axis in JPL
        target.eccentricity = self.catalog_data['e'][0]  # eccentricity in JPL
        # epoch Julian Date in JPL
        target.epoch_of_elements = self.jd_to_mjd(self.catalog_data['datetime_jd'][0])
        target.epoch_of_perihelion = self.jd_to_mjd(self.catalog_data['Tp_jd'][0])  # time of periapsis in JPL
        target.perihdist = self.catalog_data['q'][0]  # periapsis distance in JPL
        # undocumented in JPL astroquery column names -- presuming P is the orbital period in JPL
        target.ephemeris_period = self.catalog_data['P'][0]
        return target
