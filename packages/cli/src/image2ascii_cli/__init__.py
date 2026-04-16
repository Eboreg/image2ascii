import logging
import sys
from importlib.metadata import version

from image2ascii_cli.cli import cli
from image2ascii_cli.config import Config
from image2ascii_cli.plugin import Plugin


__version__ = version("image2ascii-cli")
__all__ = ["cli", "Config", "Plugin"]

# Logging everything above INFO level to stderr, the rest to stdout:
__stderr_handler = logging.StreamHandler(sys.stderr)
__stderr_handler.addFilter(lambda r: r.levelno > logging.INFO)
__stdout_handler = logging.StreamHandler(sys.stdout)
__stdout_handler.addFilter(lambda r: r.levelno <= logging.INFO)

logger = logging.getLogger(__name__)
logger.addHandler(__stderr_handler)
logger.addHandler(__stdout_handler)
logger.setLevel(logging.INFO)
