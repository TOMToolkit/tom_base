from specutils import Spectrum
from astropy.units import Quantity


class SpectrumSerializer():

    def serialize(self, spectrum: Spectrum) -> dict:
        """
        Serializes a Spectrum in order to store in a ReducedDatum object. The serialization stores only what's
        necessary to rebuild the Spectrum--namely, flux and wavelength, and their respective units.

        :param spectrum: Spectrum to be serialized
        :type spectrum: specutils.Spectrum

        :returns: JSON representation of spectrum
        :rtype: dict
        """
        serialized = {}
        serialized['flux'] = spectrum.flux.value.tolist()
        serialized['flux_units'] = spectrum.flux.unit.to_string()
        serialized['wavelength'] = spectrum.wavelength.value.tolist()
        serialized['wavelength_units'] = spectrum.wavelength.unit.to_string()
        return serialized

    def deserialize(self, spectrum: dict) -> Spectrum:
        """
        Constructs a Spectrum from the spectrum value stored in a ReducedDatum

        :param spectrum: JSON representation used to construct the Spectrum
        :type spectrum: dict

        :returns: Spectrum representing the spectrum information
        :rtype: specutil.Spectrum
        """
        flux = Quantity(value=spectrum['flux'], unit=spectrum['flux_units'])
        wavelength = Quantity(value=spectrum['wavelength'], unit=spectrum['wavelength_units'])
        spectrum = Spectrum(flux=flux, spectral_axis=wavelength)
        return spectrum
