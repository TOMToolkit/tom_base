import logging
import mimetypes

from astropy import units
import astropy.io.ascii
from astropy.time import Time, TimezoneInfo

from tom_dataproducts.data_processor import DataProcessor
from tom_dataproducts.exceptions import InvalidFileFormatException

logger = logging.getLogger(__name__)
# logger.setLevel(logging.DEBUG)


class PanstarrsProcessor(DataProcessor):

    def data_type_override(self):
        return 'photometry'

    def process_data(self, data_product):
        """
        Routes a PanSTARRS processing call to a method specific to a file-format.

        The call site for this method is (typically) tom_dataproducts.data_processor.run_data_processor(),
        where the returned list of datums is used to `bulk_create` ReducedDatum objects.

        :param data_product: Photometric DataProduct which will be processed into the specified format for database
        ingestion
        :type data_product: DataProduct

        :returns: python list of 3-tuples: (timestamp, datum, source)
        :rtype: list
        """

        mimetype = mimetypes.guess_type(data_product.data.path)[0]
        logger.debug(f'Processing PanSTARRS data with mimetype {mimetype}')

        if mimetype in self.PLAINTEXT_MIMETYPES:
            photometry = self._process_photometry_from_plaintext(data_product)
            return [(datum.pop('timestamp'), datum, datum.pop('source', 'PanSTARRS')) for datum in photometry]
        else:
            raise InvalidFileFormatException('Unsupported file type')

    def _process_photometry_from_plaintext(self, data_product):
        """
        Processes the photometric data from a plaintext file into a list of dicts. File is read using astropy as
        specified in the below documentation. The file is expected to be a multi-column delimited comma delimited
        text file (csv), as produced by the PanSTARRS (MAST PS1) Main Catalog photometry service.

        NOTE: currently this method makes assumptions about the column names and order of the columns in the file.
        TODO: should be generalized to use the panstarrs_api.py module to get the column names.

        :param data_product: PanSTARRS Photometric DataProduct which will be processed into a list of dicts
        :type data_product: DataProduct

        :returns: python list containing the photometric data from the DataProduct
        :rtype: list
        """
        photometry = []

        data = astropy.io.ascii.read(data_product.data.path)
        if len(data) < 1:
            raise InvalidFileFormatException('Empty table or invalid file type')

        try:
            for datum in data:
                # extract the timestamp from the epochMean column
                time = Time(float(datum['epochMean']), format='mjd')
                utc = TimezoneInfo(utc_offset=0*units.hour)
                time.format = 'datetime'
                timestamp = time.to_datetime(timezone=utc)
                for optical_filter in ['g', 'r', 'i', 'z', 'y']:
                    # these filter and column names come from pastarrs_api.py
                    mag_col_name = f'{optical_filter}MeanPSFMag'
                    mag_err_col_name = f'{optical_filter}MeanPSFMagErr'
                    mag = float(datum[mag_col_name])
                    mag_err = float(datum[mag_err_col_name])
                    # -999 is the value returned by PanSTARRS when there is no data for a given column
                    # so, filter out columns for which there is no data
                    if mag > -999:
                        value = {
                            'timestamp': timestamp,
                            'telescope': 'PanSTARRS 1',
                            'magnitude': mag,
                            'error': mag_err,
                            'filter': optical_filter,
                        }
                        photometry.append(value)
        except Exception as e:
            raise InvalidFileFormatException(e)

        return photometry
