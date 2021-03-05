from specutils import Spectrum1D
from astropy.units import Quantity


class SpectrumSerializer():

    def serialize(self, spectrum: Spectrum1D) -> dict:
        """
        Serializes a Spectrum1D in order to store in a ReducedDatum object. The serialization stores only what's
        necessary to rebuild the Spectrum1D--namely, flux and wavelength, and their respective units.

        :param spectrum: Spectrum1D to be serialized
        :type spectrum: specutils.Spectrum1D

        :returns: JSON representation of spectrum
        :rtype: dict
        """
        serialized = {}
        serialized['flux'] = spectrum.flux.value.tolist()
        serialized['flux_units'] = spectrum.flux.unit.to_string()
        serialized['wavelength'] = spectrum.wavelength.value.tolist()
        serialized['wavelength_units'] = spectrum.wavelength.unit.to_string()
        return serialized

    def deserialize(self, spectrum: dict) -> Spectrum1D:
        """
        Constructs a Spectrum1D from the spectrum value stored in a ReducedDatum

        :param spectrum: JSON representation used to construct the Spectrum1D
        :type spectrum: dict

        :returns: Spectrum1D representing the spectrum information
        :rtype: specutil.Spectrum1D
        """
        flux = Quantity(value=spectrum['flux'], unit=spectrum['flux_units'])
        wavelength = Quantity(value=spectrum['wavelength'], unit=spectrum['wavelength_units'])
        spectrum = Spectrum1D(flux=flux, spectral_axis=wavelength)
        return spectrum
