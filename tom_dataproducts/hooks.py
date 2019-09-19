import logging

logger = logging.getLogger(__name__)


def data_product_post_upload(dp):
    logger.info('Running post upload hook for DataProduct: {}'.format(dp))
