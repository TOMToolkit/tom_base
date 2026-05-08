import logging
import mimetypes

from django.conf import settings
from importlib import import_module

from tom_dataproducts.models import try_parse_reduced_datum
from tom_targets.sharing import continuous_share_data

logger = logging.getLogger(__name__)


DEFAULT_DATA_PROCESSOR_CLASS = 'tom_dataproducts.data_processor.DataProcessor'


def run_data_processor(dp, dp_type_override=None):
    """
    Reads the `data_product_type` from the dp parameter and imports the corresponding `DATA_PROCESSORS` specified in
    `settings.py`, then runs `process_data` and inserts the returned values into the database.

    :param dp: DataProduct which will be processed into a list
    :type dp: DataProduct

    :param dp_type_override: Optional. DataProduct type to override with. If None, the
    type from the `dp` object is used.
    :type dp_type_override: str, optional

    :returns: List of typed ReducedDatum objects created by the `run_data_processor` call
    :rtype: list
    """
    data_type = dp_type_override or dp.data_product_type
    try:
        processor_class = settings.DATA_PROCESSORS[data_type]
    except Exception:
        processor_class = DEFAULT_DATA_PROCESSOR_CLASS

    try:
        mod_name, class_name = processor_class.rsplit('.', 1)
        mod = import_module(mod_name)
        clazz = getattr(mod, class_name)
    except (ImportError, AttributeError):
        raise ImportError('Could not import {}. Did you provide the correct path?'.format(processor_class))

    data_processor = clazz()
    # 1. data returned by process_data is a list of 3-tuples: (timestamp, datum, source)
    data = data_processor.process_data(dp)
    data_type = data_processor.data_type_override() or data_type

    # 2. Build typed ReducedDatum instances from the raw data.
    # try_parse_reduced_datum inspects the data_type and field names to determine the
    # correct concrete subclass (photometry, spectroscopy, astrometry, or generic).
    new_reduced_datums = []
    for datum in data:
        instance = try_parse_reduced_datum({
            'target': dp.target,
            'data_product': dp,
            'timestamp': datum[0],
            'source_name': datum[2],
            'data_type': data_type,
            **datum[1],
        })
        new_reduced_datums.append(instance)

    # 3. bulk_create requires a uniform model type, so group instances by their concrete class.
    # Then create them
    by_type: dict[type, list] = {}
    for instance in new_reduced_datums:
        by_type.setdefault(type(instance), []).append(instance)

    reduced_datums = []
    for model_class, instances in by_type.items():
        # ignore_conflicts uses DB level cosntraints for deduplication
        reduced_datums.extend(model_class.objects.bulk_create(instances, ignore_conflicts=True))

    # 4. Trigger any sharing you may have set to occur when new data comes in
    # Encapsulate this in a try/catch so sharing failure doesn't prevent dataproduct ingestion
    try:
        continuous_share_data(dp.target, reduced_datums)
    except Exception as e:
        logger.warning(f"Failed to share new dataproduct {dp.product_id}: {repr(e)}")

    # log what happened
    logger.info(f'{len(reduced_datums)} of {len(data)} new ReducedDatums added for DataProduct: {dp.product_id}')

    return reduced_datums


class DataProcessor():

    FITS_MIMETYPES = ['image/fits', 'application/fits']
    PLAINTEXT_MIMETYPES = ['text/plain', 'text/csv']

    mimetypes.add_type('image/fits', '.fits')
    mimetypes.add_type('image/fits', '.fz')
    mimetypes.add_type('application/fits', '.fits')
    mimetypes.add_type('application/fits', '.fz')

    def process_data(self, data_product):
        """
        Routes a photometry processing call to a method specific to a file-format. This method is expected to be
        implemented by any subclasses.

        :param data_product: DataProduct which will be processed into a list
        :type data_product: DataProduct

        :returns: python list of 2-tuples, each with a timestamp and corresponding data
        :rtype: list of 2-tuples
        """
        return []

    def data_type_override(self):
        """
        Override for the ReducedDatum data type, if you want it to be different from the
        DataProduct data_type.
        """
        return ''
