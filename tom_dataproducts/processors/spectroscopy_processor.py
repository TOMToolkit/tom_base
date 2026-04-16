import json
import mimetypes
import numpy as np

from datetime import datetime

from astropy import units
from astropy.io import fits, ascii as astropy_ascii
from astropy.time import Time
from astropy.wcs import WCS
from specutils import Spectrum

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
            spectrum, obs_date, source_id = self._process_spectrum_from_fits(data_product)
        elif mimetype in self.PLAINTEXT_MIMETYPES:
            spectrum, obs_date, source_id = self._process_spectrum_from_plaintext(data_product)
        else:
            raise InvalidFileFormatException('Unsupported file type')

        serialized_spectrum = SpectrumSerializer().serialize(spectrum)

        return [(obs_date, serialized_spectrum, source_id)]

    def _process_spectrum_from_fits(self, data_product):
        """
        Processes the data from a spectrum from a fits file into a Spectrum object, which can then be serialized and
        stored as a ReducedDatum for further processing or display. File is read using specutils as specified in the
        below documentation.
        # https://specutils.readthedocs.io/en/doc-testing/specutils/read_fits.html

        :param data_product: Spectroscopic DataProduct which will be processed into a Spectrum
        :type data_product: tom_dataproducts.models.DataProduct

        :returns: Spectrum object containing the data from the DataProduct
        :rtype: specutils.Spectrum

        :returns: Datetime of observation, if it is in the header and the file is from a supported facility, current
            datetime otherwise
        :rtype: AstroPy.Time
        """
        facility_name = 'DEFAULT'

        flux, header = fits.getdata(data_product.data.path, header=True)

        for facility_class in get_service_classes():
            facility = get_service_class(facility_class)()
            if facility.is_fits_facility(header):
                facility_name = facility_class
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

        spectrum = Spectrum(flux=flux, wcs=wcs)

        return spectrum, Time(date_obs).to_datetime(), facility_name

    def _process_spectrum_from_plaintext(self, data_product):
        """
        Processes the data from a spectrum from a plaintext file into a Spectrum object, which can then be serialized
        and stored as a ReducedDatum for further processing or display. File is read using astropy as specified in
        the below documentation. The file is expected to be a multi-column delimited file, with headers for wavelength
        and flux. The file also requires comments containing, at minimum, 'DATE-OBS: [value]', where value is an
        Astropy Time module-readable date. It can optionally contain 'FACILITY: [value]', where the facility is a string
        matching the name of a valid facility in the TOM.
        # http://docs.astropy.org/en/stable/io/ascii/read.html

        Alternatively, It can also process raw ascii files of data if the other information has been provided in the
        DataProduct's extra_data field as a json serialized dict of keys like 'date_obs', 'wavelength_units',
        'flux_units'.

        Parameters
        ----------
        :param data_product: Spectroscopic DataProduct which will be processed into a Spectrum
        :type data_product: tom_dataproducts.models.DataProduct

        :returns: Spectrum object containing the data from the DataProduct
        :rtype: specutils.Spectrum

        :returns: Datetime of observation, if it is in the comments and the file is from a supported facility, current
            datetime otherwise
        :rtype: AstroPy.Time
        """

        data = astropy_ascii.read(data_product.data.path)
        if len(data) < 1:
            raise InvalidFileFormatException('Empty table or invalid file type')
        # Having a facility name of None will fail to ingest the data completely, so lets see if we can find a name
        facility_name = ''
        date_obs = datetime.now()
        # Attempt to get json serialized data within the DataProduct's extra_data field
        try:
            extra_data = json.loads(data_product.extra_data)
        except json.JSONDecodeError:
            # Field is empty or not a JSON serialized string
            extra_data = None

        comments = data.meta.get('comments', [])

        for comment in comments:
            if 'date-obs' in comment.lower():
                date_obs = comment.split(':')[1].strip()
            if 'facility' in comment.lower():
                facility_name = comment.split(':')[1].strip()

        facility = get_service_class(facility_name)() if facility_name else None
        # Try to find what is needed within the text file itself first
        # If that fails, try to find it in the data products extra_data
        # If that fails, use the default values
        if facility:
            wavelength_units = facility.get_wavelength_units()
        elif extra_data and 'wavelength_units' in extra_data:
            wavelength_units = units.Unit(extra_data['wavelength_units'])
        else:
            wavelength_units = self.DEFAULT_WAVELENGTH_UNITS
        if facility:
            flux_constant = facility.get_flux_constant()
        elif extra_data and 'flux_units' in extra_data:
            flux_constant = units.Unit(extra_data['flux_units'])
        else:
            flux_constant = self.DEFAULT_FLUX_CONSTANT

        try:
            spectral_axis = np.array(data['wavelength']) * wavelength_units
            flux = np.array(data['flux']) * flux_constant
        except KeyError:
            spectral_axis = np.array(data.columns[0]) * wavelength_units
            flux = np.array(data.columns[1]) * flux_constant

        spectrum = Spectrum(flux=flux, spectral_axis=spectral_axis)

        if not facility_name and extra_data and 'source_name' in extra_data:
            facility_name = extra_data.get('source_name', '')

        return spectrum, Time(date_obs).to_datetime(), facility_name
