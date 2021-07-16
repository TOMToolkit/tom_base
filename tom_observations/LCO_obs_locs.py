from astroplan import Observer
import astropy.units as u


def choose_loc(location):
    loc_list = {
        "COJ": Observer(longitude=149.071111*u.deg, latitude=-31.273333*u.deg, elevation=1116*u.m,
                        name="Siding Spring Observatory"),
        "CPT": Observer(longitude=20.81*u.deg, latitude=-32.38*u.deg, elevation=1760*u.m,
                        name="South African Astronomical Observatory"),
        "TFN": Observer(longitude=-16.509722*u.deg, latitude=28.3*u.deg, elevation=2330*u.m,
                        name="Teide Observatory"),
        "LSC": Observer(longitude=-70.804722*u.deg, latitude=-30.1675*u.deg, elevation=2198*u.m,
                        name="Cerro Tololo Interamerican Observatory"),
        "ELP": Observer(longitude=-104.02*u.deg, latitude=30.67*u.deg, elevation=2070*u.m,
                        name="McDonald Observatory"),
        "OGG": Observer(longitude=-156.256111*u.deg, latitude=20.7075*u.deg, elevation=3055*u.m,
                        name="Haleakala Observatory"),
        "TLV": Observer(longitude=34.763333*u.deg, latitude=30.595833*u.deg, elevation=875*u.m,
                        name="Wise Observatory"),
        "NGQ": Observer(longitude=80.016667*u.deg, latitude=32.316667*u.deg, elevation=5100*u.m,
                        name="Ali Observatory")
    }

    if location in loc_list:
        return loc_list[location]
