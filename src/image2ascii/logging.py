import logging
import sys


# Logging everything above INFO level to stderr, the rest to stdout:
stderr_handler = logging.StreamHandler(sys.stderr)
stderr_handler.addFilter(lambda r: r.levelno > logging.INFO)

stdout_handler = logging.StreamHandler(sys.stdout)
stdout_handler.addFilter(lambda r: r.levelno <= logging.INFO)


def get_logger(name: str) -> logging.Logger:
    logger = logging.getLogger(name)

    logger.addHandler(stderr_handler)
    logger.addHandler(stdout_handler)
    logger.setLevel(logging.INFO)

    return logger
