import logging

logger = logging.getLogger(__name__)


def data_product_post_upload(dp):
    logger.info(f'Running post upload hook for DataProduct: {dp}')


def data_product_post_save(dps):
    logger.info(f'Running post save hook for DataProduct: {dps}')
