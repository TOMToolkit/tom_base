from django.db import migrations, models

from tom_dataproducts.processors.data_serializers import SpectrumSerializer

"""
def photon_spectrum_to_energy_spectrum(wavelength, photon_counts):
    photon_spectrum = specutils.Spectrum1D(flux=photon_counts, spectral_axis=wavelength)
    energy_spectrum = photon_spectrum.flux * (photon_spectrum.energy / u.photon)
    return specutils.Spectrum1D(spectral_axis=wavelength, flux=energy_spectrum.to('erg / (s cm2 AA)', u.spectral_density(wavelength)))
"""

def photon_spectrum_to_energy_spectrum(apps, schema_editor):
    data_products = apps.get_model('tom_dataproducts', 'DataProduct')
    spectrum_serializer = SpectrumSerializer()
    for row in data_products.objects.all():
        photon_spectrum = spectrum_serializer.deserialize(row.value)
        energy_spectrum = photon_spectrum.flux * (photon_spectrum.energy / u.photon)
        energy_spectrum_object = specutils.Spectrum1D(
                                    spectral_axis=wavelength, 
                                    flux=energy_spectrum.to('erg / (s cm2 AA)', u.spectral_density(wavelength)))
        row.value = spectrum_serializer.serialize(energy_spectrum_object)
        row.save()
        


class Migration(migrations.Migration):
    dependencies = [
        ('tom_dataproducts', '0009_auto_20210204_2221.py')
    ]

    operations = [
        migrations.RunPython(photon_spectrum_to_energy_spectrum, reverse_code=migrations.RunPython.noop),
    ]