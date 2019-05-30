import re
import json

from astropy.time import Time
from astropy.io import fits
from astropy.wcs import WCS
from astropy import units as u
from specutils import Spectrum1D

from .models import DataProduct, ReducedDatum
from tom_observations.facility import get_service_class
from .exceptions import InvalidFileFormatException


def process_data_product(data_product, target, facility=None, timestamp=None):
    try:
        if data_product.tag == 'photometry':
            with data_product.data.file.open() as f:
                for line in f:
                    # TODO: Make processing separator- and column-ordering-agnostic
                    photometry_datum = [datum.strip() for datum in re.split(',', line.decode('UTF-8'))]
                    time = Time(float(photometry_datum[0]), format='mjd')
                    time.format = 'datetime'
                    value = {
                        'magnitude': photometry_datum[2],
                        'filter': photometry_datum[1],
                        'error': photometry_datum[3]
                    }
                    ReducedDatum.objects.create(
                        target=target,
                        data_product=data_product,
                        data_type=data_product.tag,
                        timestamp=time.value,
                        value=json.dumps(value)
                    )
        elif data_product.tag == 'spectroscopy':
            spectrum = {}

            if data_product.get_file_extension() in DataProduct.FITS_EXTENSIONS.keys():
                # https://specutils.readthedocs.io/en/doc-testing/specutils/read_fits.html
                # TODO: make sure this works with compressed fits
                # TODO: make sure this works with alternate delta wavelength header
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
                # TODO: flux density differs by instrument, this needs to go in the facility-specific module
                flux = flux * get_service_class(facility)().get_flux_density()
                # flux = flux * (u.erg / (u.cm ** 2 * u.second * u.angstrom))
                spec_data = Spectrum1D(flux=flux, wcs=wcs)
                for i in range(len(spec_data.wavelength)):
                    spectrum[i] = {
                        'wavelength': spec_data.wavelength[i].value,
                        'flux': spec_data.flux[i].value
                    }
            else:
                index = 0
                with data_product.data.file.open() as f:
                    for line in f:
                        spectral_sample = [sample.strip() for sample in re.split('[\s,|;]', line.decode('UTF-8'))]
                        spectrum[str(index)] = ({
                            'wavelength': spectral_sample[0],
                            'flux': spectral_sample[1]
                        })
                        index += 1
            ReducedDatum.objects.create(
                target=target,
                data_product=data_product,
                data_type=data_product.tag,
                timestamp=timestamp,
                value=json.dumps(spectrum)
            )
    except Exception:
        raise InvalidFileFormatException
