import json

from importlib import import_module
from django.conf import settings

from .data_serializers import SpectrumSerializer
from .models import ReducedDatum, SPECTROSCOPY, PHOTOMETRY

DEFAULT_DATA_PROCESSOR_CLASS = 'tom_dataproducts.data_processor.DataProcessor'


def data_product_post_upload(dp, observation_timestamp, facility):
    try:
        processor_class = settings.DATA_PROCESSOR_CLASS
    except:
        processor_class = DEFAULT_DATA_PROCESSOR_CLASS

    try:
        mod_name, class_name = processor_class.rsplit('.', 1)
        mod = import_module(mod_name)
        clazz = getattr(mod, class_name)
    except (ImportError, AttributeError):
        raise ImportError('Could not import {}. Did you provide the correct path?'.format(processor_class))
    data_processor = clazz()

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
            for datum in photometry_datum:
                ReducedDatum.objects.create(
                    target=dp.target,
                    data_product=dp,
                    data_type=dp.tag,
                    timestamp=time,
                    value=json.dumps(datum)
                )
