import mimetypes
from datetime import datetime
from astropy.time import Time, TimezoneInfo
from astropy import units
from astropy.io import fits, ascii
from astropy.wcs import WCS
from specutils import Spectrum1D
from django.conf import settings
from importlib import import_module
import numpy as np
import json

from tom_observations.facility import get_service_class, get_service_classes
from .exceptions import InvalidFileFormatException
from .models import ReducedDatum, SPECTROSCOPY, PHOTOMETRY
from .data_serializers import SpectrumSerializer


FITS_MIMETYPES = ['image/fits', 'application/fits']
PLAINTEXT_MIMETYPES = ['text/plain', 'text/csv']
DEFAULT_WAVELENGTH_UNITS = units.angstrom
DEFAULT_FLUX_CONSTANT = units.erg / units.cm ** 2 / units.second / units.angstrom
DEFAULT_DATA_PROCESSOR_CLASS = 'tom_dataproducts.data_processor.DataProcessor'

mimetypes.add_type('image/fits', '.fits')
mimetypes.add_type('image/fits', '.fz')
mimetypes.add_type('application/fits', '.fits')
mimetypes.add_type('application/fits', '.fz')


def run_data_processor(dp):
    try:
        processor_class = settings.DATA_PROCESSOR_CLASS
    except Exception:
        processor_class = DEFAULT_DATA_PROCESSOR_CLASS

    try:
        mod_name, class_name = processor_class.rsplit('.', 1)
        mod = import_module(mod_name)
        clazz = getattr(mod, class_name)
    except (ImportError, AttributeError):
        raise ImportError('Could not import {}. Did you provide the correct path?'.format(processor_class))
    data_processor = clazz()

    if dp.tag == SPECTROSCOPY[0]:
        spectrum, obs_date = data_processor.process_spectroscopy(dp)
        serialized_spectrum = SpectrumSerializer().serialize(spectrum)
        ReducedDatum.objects.create(
            target=dp.target,
            data_product=dp,
            data_type=dp.tag,
            timestamp=obs_date,
            value=serialized_spectrum
        )
    elif dp.tag == PHOTOMETRY[0]:
        photometry = data_processor.process_photometry(dp)
        for time, photometry_datum in photometry.items():
            for datum in photometry_datum:
                ReducedDatum.objects.create(
                    target=dp.target,
                    data_product=dp,
                    data_type=dp.tag,
                    timestamp=time,
                    value=json.dumps(datum)
                )


class DataProcessor():

    def process_spectroscopy(self, data_product):
        """
        Routes a spectrum processing call to a method specific to a file-format.

        :param data_product: Spectroscopic DataProduct which will be processed into a Spectrum1D
        :type data_product: tom_dataproducts.models.DataProduct

        :returns: Spectrum1D object containing the data from the DataProduct
        :rtype: specutils.Spectrum1D

        :returns: Datetime of observation
        :rtype: AstroPy.Time

        :raises: InvalidFileFormatException
        """

        mimetype = mimetypes.guess_type(data_product.data.path)[0]
        if mimetype in FITS_MIMETYPES:
            return self._process_spectrum_from_fits(data_product)
        elif mimetype in PLAINTEXT_MIMETYPES:
            return self._process_spectrum_from_plaintext(data_product)
        else:
            raise InvalidFileFormatException('Unsupported file type')

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
                date_obs = facility.get_date_obs(header)
                break
        else:
            flux_constant = DEFAULT_FLUX_CONSTANT
            date_obs = datetime.now()

        dim = len(flux.shape)
        if dim == 3:
            flux = flux[0, 0, :]
        elif flux.shape[0] == 2:
            flux = flux[0, :]
        header['CUNIT1'] = 'Angstrom'
        wcs = WCS(header=header)
        flux = flux * flux_constant

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
        wavelength_units = facility.get_wavelength_units() if facility else DEFAULT_WAVELENGTH_UNITS
        flux_constant = facility.get_flux_constant() if facility else DEFAULT_FLUX_CONSTANT

        spectral_axis = np.array(data['wavelength']) * wavelength_units
        flux = np.array(data['flux']) * flux_constant
        spectrum = Spectrum1D(flux=flux, spectral_axis=spectral_axis)

        return spectrum, Time(date_obs).to_datetime()

    def process_photometry(self, data_product):
        """
        Routes a photometry processing call to a method specific to a file-format.

        :param data_product: Photometric DataProduct which will be processed into a dict
        :type data_product: DataProduct

        :returns: python dict containing the data from the DataProduct
        :rtype: dict
        """

        mimetype = mimetypes.guess_type(data_product.data.path)[0]
        if mimetype in PLAINTEXT_MIMETYPES:
            return self._process_photometry_from_plaintext(data_product)
        else:
            raise InvalidFileFormatException('Unsupported file type')

    def _process_photometry_from_plaintext(self, data_product):
        """
        Processes the photometric data from a plaintext file into a dict, which can then be  stored as a ReducedDatum
        for further processing or display. File is read using astropy as specified in the below documentation. The file
        is expected to be a multi-column delimited file, with headers for time, magnitude, filter, and error.
        # http://docs.astropy.org/en/stable/io/ascii/read.html

        :param data_product: Photometric DataProduct which will be processed into a dict
        :type data_product: DataProduct

        :returns: python dict containing the data from the DataProduct
        :rtype: dict
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
