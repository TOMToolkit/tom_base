import mimetypes

from astropy import units
from astropy.io import ascii
from astropy.time import Time, TimezoneInfo

from bhtom_base.bhtom_dataproducts.data_processor import DataProcessor
from bhtom_base.bhtom_dataproducts.exceptions import InvalidFileFormatException
from bhtom_base.bhtom_dataproducts.models import DatumValue
from typing import List, Tuple
from datetime import datetime


class PhotometryProcessor(DataProcessor):

    def process_data(self, data_product) -> List[Tuple[datetime, DatumValue]]:
        """
        Routes a photometry processing call to a method specific to a file-format.

        :param data_product: Photometric DataProduct which will be processed into the specified format for database
        ingestion
        :type data_product: DataProduct

        :returns: python list of 2-tuples, each with a timestamp and corresponding data
        :rtype: list
        """

        mimetype = mimetypes.guess_type(data_product.data.path)[0]
        if mimetype in self.PLAINTEXT_MIMETYPES:
            return self._process_photometry_from_plaintext(data_product)
        else:
            raise InvalidFileFormatException('Unsupported file type')

    def _process_photometry_from_plaintext(self, data_product) -> List[Tuple[datetime, DatumValue]]:
        """
        Processes the photometric data from a plaintext file into a list of dicts. File is read using astropy as
        specified in the below documentation. The file is expected to be a multi-column delimited file, with headers for
        time, magnitude, filter, and error.
        # http://docs.astropy.org/en/stable/io/ascii/read.html

        :param data_product: Photometric DataProduct which will be processed into a list of dicts
        :type data_product: DataProduct

        :returns: python list containing the photometric data from the DataProduct
        :rtype: list
        """

        photometry = []

        data = ascii.read(data_product.data.path)
        if len(data) < 1:
            raise InvalidFileFormatException('Empty table or invalid file type')

        for datum in data:
            time = Time(float(datum['time']), format='mjd')
            utc = TimezoneInfo(utc_offset=0 * units.hour)
            value: DatumValue = DatumValue(
                mjd=time.mjd,
                data_type='photometry',
                value=datum['magnitude'],
                filter=datum['filter'],
                error=datum['error']
            )
            photometry.append((time.to_datetime(timezone=utc), value))

        return photometry
