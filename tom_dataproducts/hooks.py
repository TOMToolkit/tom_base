import logging

logger = logging.getLogger(__name__)


def data_product_post_upload(dp):
    """
    This hook runs following uploading a data product via the DataProductUploadView.
    """
    logger.info(f'Running post upload hook for DataProduct: {dp}')


def data_product_post_save(dps):
    """
    This hook runs following saving a data product via the DataProductSaveView.
    """
    logger.info(f'Running post save hook for DataProduct: {dps}')


def multiple_data_products_post_save(dps):
    """
    This hook runs following saving multiple data products via the DataProductSaveView.
    """
    logger.info(f'Running post save hook for multiple DataProducts: {dps}')
