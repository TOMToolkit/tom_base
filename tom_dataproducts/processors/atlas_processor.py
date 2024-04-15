import mimetypes

from astropy import units
import astropy.io.ascii
from astropy.time import Time, TimezoneInfo
import numpy as np

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

        :returns: python list of 3-tuples, each with a timestamp and corresponding data, and source
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
        See https://fallingstar-data.com/forcedphot/resultdesc/ for a description of the output format.

        The header looks like this:
        ###MJD   m   dm  uJy   duJy F err chi/N   RA  Dec   x   y  maj  min   phi  apfit mag5sig Sky   Obs

        :param data_product: ATLAS Photometric DataProduct which will be processed into a list of dicts
        :type data_product: DataProduct

        :returns: python list containing the photometric data from the DataProduct
        :rtype: list
        """
        photometry = []
        signal_to_noise_cutoff = 3.0  # cutoff to turn magnitudes into non-detection limits

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
                    'filter': str(datum['F']),
                    'telescope': 'ATLAS',
                }
                # If the signal is in the noise, calculate the non-detection limit from the reported flux uncertainty.
                # see https://fallingstar-data.com/forcedphot/resultdesc/
                signal_to_noise = float(datum['uJy']) / float(datum['duJy'])
                if signal_to_noise <= signal_to_noise_cutoff:
                    value['limit'] = 23.9 - 2.5 * np.log10(signal_to_noise_cutoff * float(datum['duJy']))
                else:
                    value['magnitude'] = float(datum['m'])
                    value['error'] = float(datum['dm'])

                photometry.append(value)
        except Exception as e:
            raise InvalidFileFormatException(e)

        return photometry
