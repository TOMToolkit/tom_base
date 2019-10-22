import mimetypes

from django.conf import settings
from importlib import import_module


DEFAULT_DATA_PROCESSOR_CLASS = 'tom_dataproducts.data_processor.DataProcessor'


def run_data_processor(dp):

    try:
        processor_class = settings.DATA_PROCESSORS[dp.data_product_type]
    except Exception:
        processor_class = DEFAULT_DATA_PROCESSOR_CLASS

    print(processor_class)

    try:
        mod_name, class_name = processor_class.rsplit('.', 1)
        print(mod_name)
        print(class_name)
        mod = import_module(mod_name)
        print(mod)
        clazz = getattr(mod, class_name)
        print(clazz)
    except (ImportError, AttributeError):
        raise ImportError('Could not import {}. Did you provide the correct path?'.format(processor_class))

    print(clazz)

    data_processor = clazz()
    data_processor.process_data(dp)

    # if dp.data_product_type == settings.DATA_PRODUCT_TYPES['spectroscopy'][0]:
    #     spectrum, obs_date = data_processor.process_spectroscopy(dp)
    #     serialized_spectrum = SpectrumSerializer().serialize(spectrum)
    #     ReducedDatum.objects.create(
    #         target=dp.target,
    #         data_product=dp,
    #         data_type=dp.data_product_type,
    #         timestamp=obs_date,
    #         value=serialized_spectrum
    #     )
    # elif dp.data_product_type == settings.DATA_PRODUCT_TYPES['photometry'][0]:
    #     photometry = data_processor.process_photometry(dp)
    #     for time, photometry_datum in photometry.items():
    #         for datum in photometry_datum:
    #             ReducedDatum.objects.create(
    #                 target=dp.target,
    #                 data_product=dp,
    #                 data_type=dp.data_product_type,
    #                 timestamp=time,
    #                 value=json.dumps(datum)
    #             )


class DataProcessor():

    FITS_MIMETYPES = ['image/fits', 'application/fits']
    PLAINTEXT_MIMETYPES = ['text/plain', 'text/csv']

    mimetypes.add_type('image/fits', '.fits')
    mimetypes.add_type('image/fits', '.fz')
    mimetypes.add_type('application/fits', '.fits')
    mimetypes.add_type('application/fits', '.fz')

    def process_data(self, data_product):
        pass
