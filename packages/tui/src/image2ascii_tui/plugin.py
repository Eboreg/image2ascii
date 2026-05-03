from image2ascii.plugin import BasePlugin
from image2ascii_tui.cli import TextualSubCommand


class Plugin(BasePlugin):
    cli_subcommands = {"tui": TextualSubCommand}
