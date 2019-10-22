import mimetypes
import json

from astropy import units
from astropy.io import ascii
from astropy.time import Time, TimezoneInfo

from tom_dataproducts.data_processor import DataProcessor
from tom_dataproducts.exceptions import InvalidFileFormatException
from tom_dataproducts.models import ReducedDatum


class PhotometryProcessor(DataProcessor):

    def process_data(self, data_product):
        """
        Routes a photometry processing call to a method specific to a file-format.

        :param data_product: Photometric DataProduct which will be processed into a dict
        :type data_product: DataProduct

        :returns: python dict containing the data from the DataProduct
        :rtype: dict
        """

        mimetype = mimetypes.guess_type(data_product.data.path)[0]
        if mimetype in self.PLAINTEXT_MIMETYPES:
            photometry = self._process_photometry_from_plaintext(data_product)
            for time, photometry_datum in photometry.items():
                for datum in photometry_datum:
                    ReducedDatum.objects.create(
                        target=data_product.target,
                        data_product=data_product,
                        data_type=data_product.data_product_type,
                        timestamp=time,
                        value=json.dumps(datum)
                    )
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
