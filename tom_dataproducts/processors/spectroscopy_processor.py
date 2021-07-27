import mimetypes
import numpy as np

from datetime import datetime

from astropy import units
from astropy.io import fits, ascii
from astropy.time import Time
from astropy.wcs import WCS
from specutils import Spectrum1D

from tom_dataproducts.data_processor import DataProcessor
from tom_dataproducts.exceptions import InvalidFileFormatException
from tom_dataproducts.processors.data_serializers import SpectrumSerializer
from tom_observations.facility import get_service_class, get_service_classes


class SpectroscopyProcessor(DataProcessor):

    DEFAULT_WAVELENGTH_UNITS = units.angstrom
    DEFAULT_FLUX_CONSTANT = units.erg / units.cm ** 2 / units.second / units.angstrom

    def process_data(self, data_product):
        """
        Routes a spectroscopy processing call to a method specific to a file-format, then serializes the returned data.

        :param data_product: Spectroscopic DataProduct which will be processed into the specified format for database
        ingestion
        :type data_product: DataProduct

        :returns: python list of 2-tuples, each with a timestamp and corresponding data
        :rtype: list
        """

        mimetype = mimetypes.guess_type(data_product.data.path)[0]
        if mimetype in self.FITS_MIMETYPES:
            spectrum, obs_date = self._process_spectrum_from_fits(data_product)
        elif mimetype in self.PLAINTEXT_MIMETYPES:
            spectrum, obs_date = self._process_spectrum_from_plaintext(data_product)
        else:
            raise InvalidFileFormatException('Unsupported file type')

        serialized_spectrum = SpectrumSerializer().serialize(spectrum)

        return [(obs_date, serialized_spectrum)]

    def _process_spectrum_from_fits(self, data_product):
        """
        Processes the data from a spectrum from a fits file into a Spectrum1D object, which can then be serialized and
        stored as a ReducedDatum for further processing or display. File is read using specutils as specified in the
        below documentation.
        # https://specutils.readthedocs.io/en/doc-testing/specutils/read_fits.html

        :param data_product: Spectroscopic DataProduct which will be processed into a Spectrum1D
        :type data_product: tom_dataproducts.models.DataProduct

        :returns: Spectrum1D object containing the data from the DataProduct
        :rtype: specutils.Spectrum1D

        :returns: Datetime of observation, if it is in the header and the file is from a supported facility, current
            datetime otherwise
        :rtype: AstroPy.Time
        """

        flux, header = fits.getdata(data_product.data.path, header=True)

        for facility_class in get_service_classes():
            facility = get_service_class(facility_class)()
            if facility.is_fits_facility(header):
                flux_constant = facility.get_flux_constant()
                date_obs = facility.get_date_obs_from_fits_header(header)
                break
        else:
            flux_constant = self.DEFAULT_FLUX_CONSTANT
            date_obs = datetime.now()

        dim = len(flux.shape)
        if dim == 3:
            flux = flux[0, 0, :]
        elif flux.shape[0] == 2:
            flux = flux[0, :]
        flux = flux * flux_constant

        header['CUNIT1'] = 'Angstrom'
        wcs = WCS(header=header, naxis=1)

        spectrum = Spectrum1D(flux=flux, wcs=wcs)

        return spectrum, Time(date_obs).to_datetime()

    def _process_spectrum_from_plaintext(self, data_product):
        """
        Processes the data from a spectrum from a plaintext file into a Spectrum1D object, which can then be serialized
        and stored as a ReducedDatum for further processing or display. File is read using astropy as specified in
        the below documentation. The file is expected to be a multi-column delimited file, with headers for wavelength
        and flux. The file also requires comments containing, at minimum, 'DATE-OBS: [value]', where value is an
        Astropy Time module-readable date. It can optionally contain 'FACILITY: [value]', where the facility is a string
        matching the name of a valid facility in the TOM.
        # http://docs.astropy.org/en/stable/io/ascii/read.html

        Parameters
        ----------
        :param data_product: Spectroscopic DataProduct which will be processed into a Spectrum1D
        :type data_product: tom_dataproducts.models.DataProduct

        :returns: Spectrum1D object containing the data from the DataProduct
        :rtype: specutils.Spectrum1D

        :returns: Datetime of observation, if it is in the comments and the file is from a supported facility, current
            datetime otherwise
        :rtype: AstroPy.Time
        """

        data = ascii.read(data_product.data.path)
        if len(data) < 1:
            raise InvalidFileFormatException('Empty table or invalid file type')
        facility_name = None
        date_obs = datetime.now()
        comments = data.meta.get('comments', [])

        for comment in comments:
            if 'date-obs' in comment.lower():
                date_obs = comment.split(':')[1].strip()
            if 'facility' in comment.lower():
                facility_name = comment.split(':')[1].strip()

        facility = get_service_class(facility_name)() if facility_name else None
        wavelength_units = facility.get_wavelength_units() if facility else self.DEFAULT_WAVELENGTH_UNITS
        flux_constant = facility.get_flux_constant() if facility else self.DEFAULT_FLUX_CONSTANT

        spectral_axis = np.array(data['wavelength']) * wavelength_units
        flux = np.array(data['flux']) * flux_constant
        spectrum = Spectrum1D(flux=flux, spectral_axis=spectral_axis)

        return spectrum, Time(date_obs).to_datetime()
