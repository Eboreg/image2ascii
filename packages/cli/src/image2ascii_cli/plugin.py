from image2ascii.plugin import BasePlugin
from image2ascii_cli.config import CliFileConvertConfig, ColorGuide


class Plugin(BasePlugin):
    config_class = CliFileConvertConfig
    cli_subcommands = {"conv": CliFileConvertConfig, "colors": ColorGuide}
