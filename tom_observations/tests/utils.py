import ephem

# Site data matches built-in pyephem observer data for Los Angeles
SITES = {
    'Los Angeles': {
        'latitude': 34.052222,
        'longitude': -117.756306,
        'elevation': 86.847092
    }
}

class FakeFacility:
    name = 'Fake Facility'

    @classmethod
    def get_observing_sites(clz):
        return SITES

    @classmethod
    def get_observer_for_site(clz, site):
        return ephem.city('Los Angeles')