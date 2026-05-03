from importlib.metadata import version

from image2ascii_cli.cli import cli
from image2ascii_cli.config import CliFileConvertSettings
from image2ascii_cli.plugin import Plugin


__version__ = version("image2ascii-cli")
__all__ = ["cli", "CliFileConvertSettings", "Plugin"]
