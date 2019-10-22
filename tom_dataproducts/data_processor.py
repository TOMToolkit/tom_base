import mimetypes

from django.conf import settings
from importlib import import_module


DEFAULT_DATA_PROCESSOR_CLASS = 'tom_dataproducts.data_processor.DataProcessor'


def run_data_processor(dp):

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
    data_processor.process_data(dp)


class DataProcessor():

    FITS_MIMETYPES = ['image/fits', 'application/fits']
    PLAINTEXT_MIMETYPES = ['text/plain', 'text/csv']

    mimetypes.add_type('image/fits', '.fits')
    mimetypes.add_type('image/fits', '.fz')
    mimetypes.add_type('application/fits', '.fits')
    mimetypes.add_type('application/fits', '.fz')

    def process_data(self, data_product):
        pass
