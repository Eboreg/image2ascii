from image2ascii.plugin import BasePlugin
from image2ascii_cli.config import CliFileConvertConfig


class Plugin(BasePlugin):
    config_class = CliFileConvertConfig
