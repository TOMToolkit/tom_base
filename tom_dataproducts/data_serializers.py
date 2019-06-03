import json

from specutils import Spectrum1D
from astropy.units import Quantity


class SpectrumSerializer():

    def serialize(self, spectrum):
        serialized = {}
        serialized['photon_flux'] = spectrum.photon_flux.value.tolist()
        serialized['photon_flux_units'] = spectrum.photon_flux.unit.to_string()
        serialized['wavelength'] = spectrum.wavelength.value.tolist()
        serialized['wavelength_units'] = spectrum.wavelength.unit.to_string()
        return json.dumps(serialized)

    def deserialize(self, spectrum):
        data = json.loads(spectrum)
        flux = Quantity(value=data['photon_flux'], unit=data['photon_flux_units'])
        wavelength = Quantity(value=data['wavelength'], unit=data['wavelength_units'])
        spectrum = Spectrum1D(flux=flux, spectral_axis=wavelength)
        return spectrum
