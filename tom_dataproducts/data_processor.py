import mimetypes
from astropy.time import Time, TimezoneInfo
from astropy import units
from astropy.io import fits, ascii
from astropy.wcs import WCS
from specutils import Spectrum1D
import numpy as np

from tom_observations.facility import get_service_class
from .exceptions import InvalidFileFormatException

mimetypes.add_type('image/fits', '.fz')


class DataProcessor():

    def process_spectroscopy(self, data_product, facility):
        """
        Routes a spectrum processing call to a method specific to a file-format.

        Parameters
        ----------
        data_product : tom_dataproducts.models.DataProduct
            Spectroscopic DataProduct which will be processed into a Spectrum1D
        facility : str
            The name of the facility from which the data was taken, and should match the key in the FACILITY property in
            the TOM settings.

        Returns
        -------
        specutils.Spectrum1D
            Spectrum1D object containing the data from the DataProduct

        Raises
        ------
        InvalidFileFormatException
        """

        filetype = mimetypes.guess_type(data_product.data.path)[0]
        if filetype == 'image/fits':
            return self._process_spectrum_from_fits(data_product, facility)
        else:
            try:
                return self._process_spectrum_from_plaintext(data_product, facility)
            except Exception:
                raise InvalidFileFormatException('Unsupported file type')

    def _process_spectrum_from_fits(self, data_product, facility):
        """
        Processes the data from a spectrum from a fits file into a Spectrum1D object, which can then be serialized and
        stored as a ReducedDatum for further processing or display. File is read using specutils as specified in the
        below documentation.
        # https://specutils.readthedocs.io/en/doc-testing/specutils/read_fits.html

        Parameters
        ----------
        data_product : tom_dataproducts.models.DataProduct
            Spectroscopic DataProduct which will be processed into a Spectrum1D
        facility : str
            The name of the facility from which the data was taken, and should match the key in the FACILITY property in
            the TOM settings.

        Returns
        -------
        specutils.Spectrum1D
            Spectrum1D object containing the data from the DataProduct
        """

        flux, header = fits.getdata(data_product.data.path, header=True)

        dim = len(flux.shape)
        if dim == 3:
            flux = flux[0, 0, :]
        elif flux.shape[0] == 2:
            flux = flux[0, :]
        header['CUNIT1'] = 'Angstrom'
        wcs = WCS(header=header)
        flux = flux * get_service_class(facility)().get_flux_constant()

        spectrum = Spectrum1D(flux=flux, wcs=wcs)

        return spectrum

    def _process_spectrum_from_plaintext(self, data_product, facility):
        """
        Processes the data from a spectrum from a plaintext file into a Spectrum1D object, which can then be serialized
        and stored as a ReducedDatum for further processing or display. File is read using astropy as specified in
        the below documentation. The file is expected to be a multi-column delimited file, with headers for wavelength
        and flux.
        # http://docs.astropy.org/en/stable/io/ascii/read.html

        Parameters
        ----------
        data_product : tom_dataproducts.models.DataProduct
            Spectroscopic DataProduct which will be processed into a Spectrum1D
        facility : str
            The name of the facility from which the data was taken, and should match the key in the FACILITY property in
            the TOM settings.

        Returns
        -------
        specutils.Spectrum1D
            Spectrum1D object containing the data from the DataProduct
        """

        data = ascii.read(data_product.data.path)
        spectral_axis = np.array(data['wavelength']) * get_service_class(facility)().get_wavelength_units()
        flux = np.array(data['flux']) * get_service_class(facility)().get_flux_constant()
        spectrum = Spectrum1D(flux=flux, spectral_axis=spectral_axis)

        return spectrum

    def process_photometry(self, data_product):
        """
        Routes a photometry processing call to a method specific to a file-format.

        Parameters
        ----------
        data_product : tom_dataproducts.models.DataProduct
            Photometric DataProduct which will be processed into a dict

        Returns
        -------
        dict
            python dict containing the data from the DataProduct
        """

        try:
            return self._process_photometry_from_plaintext(data_product)
        except InvalidFileFormatException as e:
            raise e
        except Exception:
            raise InvalidFileFormatException('Could not read file')

    def _process_photometry_from_plaintext(self, data_product):
        """
        Processes the photometric data from a plaintext file into a dict, which can then be  stored as a ReducedDatum
        for further processing or display. File is read using astropy as specified in the below documentation. The file
        is expected to be a multi-column delimited file, with headers for time, magnitude, filter, and error.
        # http://docs.astropy.org/en/stable/io/ascii/read.html

        Parameters
        ----------
        data_product : tom_dataproducts.models.DataProduct
            Photometric DataProduct which will be processed into a dict

        Returns
        -------
        dict
            python dict containing the data from the DataProduct
        """

        photometry = {}

        data = ascii.read(data_product.data.path)
        if len(data) < 1:
            raise InvalidFileFormatException('Empty table or invalid file type')
        for datum in data:
            time = Time(float(datum['time']), format='mjd')
            utc = TimezoneInfo(utc_offset=0*units.hour)
            time.format = 'datetime'
            value = {
                'magnitude': datum['magnitude'],
                'filter': datum['filter'],
                'error': datum['error']
            }
            photometry.setdefault(time.to_datetime(timezone=utc), []).append(value)

        return photometry
