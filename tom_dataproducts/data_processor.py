import json
import logging
import mimetypes

from django.conf import settings
from importlib import import_module

from tom_dataproducts.models import ReducedDatum

logger = logging.getLogger(__name__)


DEFAULT_DATA_PROCESSOR_CLASS = 'tom_dataproducts.data_processor.DataProcessor'


def run_data_processor(dp):
    """
    Reads the `data_product_type` from the dp parameter and imports the corresponding `DATA_PROCESSORS` specified in
    `settings.py`, then runs `process_data` and inserts the returned values into the database.

    :param dp: DataProduct which will be processed into a list
    :type dp: DataProduct

    :returns: QuerySet of `ReducedDatum` objects created by the `run_data_processor` call
    :rtype: `QuerySet` of `ReducedDatum`
    """

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
    # data returned by process_data is a list of 3-tuples: (timestamp, datum, source)
    data = data_processor.process_data(dp)
    data_type = data_processor.data_type_override() or dp.data_product_type

    # Add only the new (non-duplicate) ReducedDatum objects to the database

    # 1. For quick O(1) lookup, create a hash table of existing ReducedDatum objects

    # Extract exising ReducedDatums for this target, and create a hash table (dict)
    # (We make the reduced_dataum.value JSONField dict hashable by converting it to a json string).
    # This is so we can do O(1) lookups below as we check for duplicate data.
    existing_reduced_datum_values = {json.dumps(rd.value, sort_keys=True, skipkeys=True): 1
                                     for rd in ReducedDatum.objects.filter(target=dp.target)}

    # 2. Create the list of new ReducedDatum objects (ready for bulk_create)
    new_reduced_datums = []
    skipped_data = []
    for datum in data:
        # Check if the value is already in the ReducedDatum table
        # (via lookup in the hash table created above for this purpose)
        if json.dumps(datum[1], sort_keys=True, skipkeys=True) in existing_reduced_datum_values:
            skipped_data.append(datum)
        else:
            new_reduced_datums.append(
                ReducedDatum(target=dp.target, data_product=dp, data_type=data_type,
                             timestamp=datum[0], value=datum[1], source_name=datum[2]))

    # prior to checking for duplicates, we created the (yet-to-be-inserted) ReducedDatum list like this:
    # reduced_datums = [ReducedDatum(target=dp.target, data_product=dp, data_type=data_type,
    #                                timestamp=datum[0], value=datum[1], source_name=datum[2]) for datum in data]

    # 3. Finally, insert the new ReducedDatum objects into the database
    ReducedDatum.objects.bulk_create(new_reduced_datums)

    # log what happened
    if skipped_data:
        logger.warning(f'{len(skipped_data)} of {len(data)} skipped as duplicates')
    logger.info(f'{len(new_reduced_datums)} of {len(data)} new ReducedDatums '
                f'added for DataProduct: {dp.product_id}')

    return ReducedDatum.objects.filter(data_product=dp)


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
