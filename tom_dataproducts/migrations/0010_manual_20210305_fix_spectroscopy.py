from astropy.units import photon, Quantity, spectral_density
from django.db import migrations
from specutils import Spectrum1D

from tom_dataproducts.processors.data_serializers import SpectrumSerializer


def photon_spectrum_to_energy_spectrum(apps, schema_editor):
    """
    This code was written by Curtis McCully for the conversion from photon_flux to flux. The below code is an adaptation
    of this code.

    def photon_spectrum_to_energy_spectrum(wavelength, photon_counts):
        photon_spectrum = specutils.Spectrum1D(flux=photon_counts, spectral_axis=wavelength)
        energy_spectrum = photon_spectrum.flux * (photon_spectrum.energy / u.photon)
        return specutils.Spectrum1D(spectral_axis=wavelength,
                                    flux=energy_spectrum.to('erg / (s cm2 AA)', u.spectral_density(wavelength)))
    """
    reduced_datum = apps.get_model('tom_dataproducts', 'ReducedDatum')
    spectrum_serializer = SpectrumSerializer()
    for row in reduced_datum.objects.filter(data_type='spectroscopy'):
        # In order to avoid a KeyError on already-corrected data or data that has no need to be corrected, we only
        # perform the spectroscopy correction on values that have photon_flux/photon_flux_units
        if all(k in row.value.keys() for k in ['photon_flux', 'photon_flux_units', 'wavelength', 'wavelength_units']):
            photon_counts = Quantity(value=row.value['photon_flux'], unit=row.value['photon_flux_units'])
            wavelength = Quantity(value=row.value['wavelength'], unit=row.value['wavelength_units'])
            photon_spectrum = Spectrum1D(flux=photon_counts, spectral_axis=wavelength)
            energy_spectrum = photon_spectrum.flux * (photon_spectrum.energy / photon)
            energy_spectrum_object = Spectrum1D(
                                        spectral_axis=wavelength,
                                        flux=energy_spectrum.to('erg / (s cm2 AA)', spectral_density(wavelength)))
            row.value = spectrum_serializer.serialize(energy_spectrum_object)
            row.save()


class Migration(migrations.Migration):
    dependencies = [
        ('tom_dataproducts', '0009_auto_20210204_2221')
    ]

    operations = [
        migrations.RunPython(photon_spectrum_to_energy_spectrum, reverse_code=migrations.RunPython.noop),
    ]