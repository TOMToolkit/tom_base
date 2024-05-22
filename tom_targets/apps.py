import logging

from tom_common.apps import TOMToolkitAppConfig

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)


class TomTargetsConfig(TOMToolkitAppConfig):
    name = 'tom_targets'
