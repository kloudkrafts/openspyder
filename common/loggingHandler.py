import logging
import logging.config

from .config import LOG_CONFIG, APP_NAME


logging.config.dictConfig(LOG_CONFIG)
logger = logging.getLogger('main')
