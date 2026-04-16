from image2ascii.plugin import BasePlugin

from image2ascii_cli.config import Config


class Plugin(BasePlugin):
    config_class = Config
