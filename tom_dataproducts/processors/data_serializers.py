import json

from specutils import Spectrum1D
from astropy.units import Quantity


class SpectrumSerializer():

    def serialize(self, spectrum):
        """
        Serializes a Spectrum1D in order to store in a ReducedDatum object. The serialization stores only what's
        necessary to rebuild the Spectrum1D--namely, photon_flux and wavelength, and their respective units.

        :param spectrum: Spectrum1D to be serialized
        :type spectrum: specutils.Spectrum1D

        :returns: JSON representation of spectrum
        :rtype: str
        """
        serialized = {}
        serialized['photon_flux'] = spectrum.photon_flux.value.tolist()
        serialized['photon_flux_units'] = spectrum.photon_flux.unit.to_string()
        serialized['wavelength'] = spectrum.wavelength.value.tolist()
        serialized['wavelength_units'] = spectrum.wavelength.unit.to_string()
        return json.dumps(serialized)

    def deserialize(self, spectrum):
        """
        Constructs a Spectrum1D from the spectrum value stored in a ReducedDatum

        :param spectrum: JSON representation used to construct the Spectrum1D
        :type spectrum: str

        :returns: Spectrum1D representing the spectrum information
        :rtype: specutil.Spectrum1D
        """
        data = json.loads(spectrum)
        flux = Quantity(value=data['photon_flux'], unit=data['photon_flux_units'])
        wavelength = Quantity(value=data['wavelength'], unit=data['wavelength_units'])
        spectrum = Spectrum1D(flux=flux, spectral_axis=wavelength)
        return spectrum
