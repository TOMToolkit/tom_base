import mimetypes

from django.conf import settings
from importlib import import_module

from tom_dataproducts.models import ReducedDatum


DEFAULT_DATA_PROCESSOR_CLASS = 'tom_dataproducts.data_processor.DataProcessor'


def run_data_processor(dp):
    """
    Reads the `data_product_type` from the dp parameter and imports the corresponding `DataProcessor` specified in
    `settings.py`, then runs `process_data` and inserts the returned values into the database.

    :param dp: DataProduct which will be processed into a list
    :type dp: DataProduct
    """

    try:
        processor_class = settings.DATA_PROCESSORS[dp.data_product_type]
    except Exception:
        processor_class = DEFAULT_DATA_PROCESSOR_CLASS

    try:
        mod_name, class_name = processor_class.rsplit('.', 1)
        mod = import_module(mod_name)
        clazz = getattr(mod, class_name)
    except (ImportError, AttributeError):
        raise ImportError('Could not import {}. Did you provide the correct path?'.format(processor_class))

    data_processor = clazz()
    data = data_processor.process_data(dp)

    for datum in data:
        ReducedDatum.objects.create(
            target=dp.target,
            data_product=dp,
            data_type=dp.data_product_type,
            timestamp=datum[0],
            value=datum[1]
        )


class DataProcessor():

    FITS_MIMETYPES = ['image/fits', 'application/fits']
    PLAINTEXT_MIMETYPES = ['text/plain', 'text/csv']

    mimetypes.add_type('image/fits', '.fits')
    mimetypes.add_type('image/fits', '.fz')
    mimetypes.add_type('application/fits', '.fits')
    mimetypes.add_type('application/fits', '.fz')

    def process_data(self, data_product):
        """
        Routes a photometry processing call to a method specific to a file-format. This method is expected to be
        implemented by any subclasses.

<<<<<<< HEAD
    def _process_spectrum_from_plaintext(self, data_product):
        """
        Processes the data from a spectrum from a plaintext file into a Spectrum1D object, which can then be serialized
        and stored as a ReducedDatum for further processing or display. File is read using astropy as specified in
        the below documentation. The file is expected to be a multi-column delimited file, with headers for wavelength
        and flux. The file also requires comments containing, at minimum, 'DATE-OBS: [value]', where value is an
        Astropy Time module-readable date. It can optionally contain 'FACILITY: [value]', where the facility is a string
        matching the name of a valid facility in the TOM.
        # http://docs.astropy.org/en/stable/io/ascii/read.html

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
=======
        :param data_product: DataProduct which will be processed into a list
>>>>>>> development
        :type data_product: DataProduct

        :returns: python list of 2-tuples, each with a timestamp and corresponding data
        :rtype: list of 2-tuples
        """
        return []
