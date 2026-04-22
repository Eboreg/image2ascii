from image2ascii.plugin import BasePlugin
from image2ascii_emoji.cli import EmojiSubCommand


class Plugin(BasePlugin):
    cli_subcommands = {"emoji": EmojiSubCommand}
