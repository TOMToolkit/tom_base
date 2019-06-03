import json

from .data_processor import DataProcessor
from .data_serializers import SpectrumSerializer
from .models import ReducedDatum, SPECTROSCOPY, PHOTOMETRY


def data_product_post_upload(dp, observation_timestamp, facility):
    processor = DataProcessor()

    if dp.tag == SPECTROSCOPY[0]:
        spectrum = processor.process_spectroscopy(dp, facility)
        serialized_spectrum = SpectrumSerializer().serialize(spectrum)
        ReducedDatum.objects.create(
            target=dp.target,
            data_product=dp,
            data_type=dp.tag,
            timestamp=observation_timestamp,
            value=serialized_spectrum
        )
    elif dp.tag == PHOTOMETRY[0]:
        photometry = processor.process_photometry(dp)
        for time, photometry_datum in photometry.items():
            ReducedDatum.objects.create(
                target=dp.target,
                data_product=dp,
                data_type=dp.tag,
                timestamp=time,
                value=json.dumps(photometry_datum)
            )
