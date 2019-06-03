import re
import magic

from astropy.time import Time
from astropy.io import fits
from astropy.wcs import WCS
from specutils import Spectrum1D

from tom_observations.facility import get_service_class
from .exceptions import InvalidFileFormatException


class DataProcessor():

    def process_spectroscopy(self, data_product, facility):
        filetype = magic.from_file(data_product.data.path, mime=True)
        if filetype == 'image/fits':
            return self._process_spectrum_from_fits(data_product, facility)
        # TODO: process into Spectrum1D file
        # elif filetype == 'text/plain':
        #     return self._process_spectrum_from_plaintext(data_product)
        else:
            raise InvalidFileFormatException('Unsupported file type')

    def _process_spectrum_from_fits(self, data_product, facility):
        # https://specutils.readthedocs.io/en/doc-testing/specutils/read_fits.html
        # TODO: make sure this works with compressed fits
        hlist = fits.open(data_product.data.file)
        hdu = hlist[0]

        flux = hdu.data

        dim = len(flux.shape)
        if dim == 3:
            flux = flux[0, 0, :]
        elif flux.shape[0] == 2:
            flux = flux[0, :]

        header = hdu.header
        header['CUNIT1'] = 'Angstrom'
        wcs = WCS(header=hdu.header)
        flux = flux * get_service_class(facility)().get_flux_density()
        spectrum = Spectrum1D(flux=flux, wcs=wcs)

        print(spectrum)

        return spectrum

    def _process_spectrum_from_plaintext(self, data_product):
        spectrum = {
            0: {}
        }

        index = 0
        with data_product.data.file.open() as f:
            for line in f:
                spectral_sample = [sample.strip() for sample in re.split('[\s,|;]', line.decode('UTF-8'))]
                spectrum[str(index)] = ({
                    'wavelength': spectral_sample[0],
                    'flux': spectral_sample[1]
                })
                index += 1

        return spectrum

    def process_photometry(self, data_product):
        filetype = magic.from_file(data_product.data.path, mime=True)
        if filetype == 'text/plain':
            self.process_photometry_from_plaintext(data_product)
        else:
            raise InvalidFileFormatException('Unsupported file type')

    def process_photometry_from_plaintext(self, data_product):
        photometry = {}
        with data_product.data.file.open() as f:
            for line in f:
                photometry_datum = [datum.strip() for datum in re.split(',', line.decode('UTF-8'))]
                time = Time(float(photometry_datum[0]), format='mjd')
                time.format = 'datetime'
                value = {
                    'magnitude': photometry_datum[2],
                    'filter': photometry_datum[1],
                    'error': photometry_datum[3]
                }
                photometry.append({'time': time, 'value': value})

        return photometry
