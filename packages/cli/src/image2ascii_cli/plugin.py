from image2ascii.plugin import BasePlugin
from image2ascii_cli.config import CliFileConvertSettings, ColorGuide


class Plugin(BasePlugin):
    cli_subcommands = {"conv": CliFileConvertSettings, "colors": ColorGuide}
