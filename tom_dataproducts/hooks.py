import json

from django.conf import settings

from .data_serializers import SpectrumSerializer
from .models import ReducedDatum, SPECTROSCOPY, PHOTOMETRY

DEFAULT_DATA_PROCESSOR_CLASS = 'tom_dataproducts.data_processor.DataProcessor'


def data_product_post_upload(dp, observation_timestamp, facility):
    try:
        processor_class = settings.DATA_PROCESSOR_CLASS
    except:
        processor_class = DEFAULT_DATA_PROCESSOR_CLASS
    data_processor = processor_class()

    if dp.tag == SPECTROSCOPY[0]:
        spectrum = data_processor.process_spectroscopy(dp, facility)
        serialized_spectrum = SpectrumSerializer().serialize(spectrum)
        ReducedDatum.objects.create(
            target=dp.target,
            data_product=dp,
            data_type=dp.tag,
            timestamp=observation_timestamp,
            value=serialized_spectrum
        )
    elif dp.tag == PHOTOMETRY[0]:
        photometry = data_processor.process_photometry(dp)
        for time, photometry_datum in photometry.items():
            ReducedDatum.objects.create(
                target=dp.target,
                data_product=dp,
                data_type=dp.tag,
                timestamp=time,
                value=json.dumps(photometry_datum)
            )
