from image2ascii.plugin import BasePlugin
from image2ascii_emoji.cli import EmojiListSubCommand, EmojiSubCommand


class Plugin(BasePlugin):
    cli_subcommands = {"emoji": EmojiSubCommand, "emoji-list": EmojiListSubCommand}
