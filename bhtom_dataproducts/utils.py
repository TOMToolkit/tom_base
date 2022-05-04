import os

from django.core.files import File

from .models import DataProduct


def create_image_dataproduct(data_product):
    """
    Creates and saves a thumbnail image for a ``DataProduct``.

    :param data_product: ``DataProduct`` for which to create an image
    :type data_product: DataProduct

    :returns: True if creation was successful
    :rtype: boolean
    """
    tmpfile = data_product.create_thumbnail()
    if tmpfile:
        dp, _ = DataProduct.objects.get_or_create(
            product_id="{}_{}".format(data_product.product_id, "jpeg"),
            target=data_product.target,
            observation_record=data_product.observation_record,
            data_product_type='image_file',
        )
        outfile_name = os.path.basename(data_product.data.file.name)
        filename = outfile_name.split(".")[0] + ".jpg"
        with open(tmpfile.name, 'rb') as f:
            dp.data.save(filename, File(f), save=True)
            dp.save()
        tmpfile.close()
        return True

    return
