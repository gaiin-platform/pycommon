import logging
import os

# Configure logging format once at module level
logging.basicConfig(format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")


def getLogger(log_stack: str):
    """
    Logger module for pycommon package.

    This module provides a centralized logging configuration for pycommon.
    It creates loggers with consistent naming and formatting, and supports
    environment-based configuration for service names and log levels.

    Environment Variables:
        SERVICE_NAME: The name of the service (default: 'amplify')
        LOG_LEVEL: The logging level (default: 'INFO')
            Supported levels: DEBUG, INFO, WARNING/WARN, ERROR, CRITICAL/FATAL

    Example:
        >>> from pycommon.logger import getLogger
        >>> logger = getLogger('my_module')
        >>> logger.info('This is a test message')
    """
    service = os.getenv("SERVICE_NAME", "amplify")
    log_level = os.getenv("LOG_LEVEL", "INFO").upper()

    level_map = {
        "DEBUG": logging.DEBUG,
        "INFO": logging.INFO,
        "WARNING": logging.WARNING,
        "WARN": logging.WARNING,  # alias
        "ERROR": logging.ERROR,
        "CRITICAL": logging.CRITICAL,
        "FATAL": logging.CRITICAL,  # alias
    }

    logger = logging.getLogger(f"{service}-{log_stack}")
    logger.setLevel(level_map.get(log_level, logging.INFO))

    return logger
