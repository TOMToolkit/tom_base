import mimetypes

from astropy import units
import astropy.io.ascii
from astropy.time import Time, TimezoneInfo

from tom_dataproducts.data_processor import DataProcessor
from tom_dataproducts.exceptions import InvalidFileFormatException


class AtlasProcessor(DataProcessor):

    def data_type_override(self):
        return 'photometry'

    def process_data(self, data_product):
        """
        Routes a atlas processing call to a method specific to a file-format.

        :param data_product: Photometric DataProduct which will be processed into the specified format for database
        ingestion
        :type data_product: DataProduct

        :returns: python list of 2-tuples, each with a timestamp and corresponding data
        :rtype: list
        """

        mimetype = mimetypes.guess_type(data_product.data.path)[0]
        if mimetype in self.PLAINTEXT_MIMETYPES:
            photometry = self._process_photometry_from_plaintext(data_product)
            return [(datum.pop('timestamp'), datum, datum.pop('source', 'ATLAS')) for datum in photometry]
        else:
            raise InvalidFileFormatException('Unsupported file type')

    def _process_photometry_from_plaintext(self, data_product):
        """
        Processes the photometric data from a plaintext file into a list of dicts. File is read using astropy as
        specified in the below documentation. The file is expected to be a multi-column delimited space delimited
        text file, as produced by the ATLAS forced photometry service at https://fallingstar-data.com/forcedphot

        The header looks like this:
        ###MJD   m   dm  uJy   duJy F err chi/N   RA  Dec   x   y  maj  min   phi  apfit mag5sig Sky   Obs

        :param data_product: ATLAS Photometric DataProduct which will be processed into a list of dicts
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
                time = Time(float(datum['##MJD']), format='mjd')
                utc = TimezoneInfo(utc_offset=0*units.hour)
                time.format = 'datetime'
                value = {
                    'timestamp': time.to_datetime(timezone=utc),
                    'magnitude': float(datum['m']),
                    'magnitude_error': float(datum['dm']),
                    'filter': str(datum['F'])
                }
                photometry.append(value)
        except Exception as e:
            raise InvalidFileFormatException(e)

        return photometry
