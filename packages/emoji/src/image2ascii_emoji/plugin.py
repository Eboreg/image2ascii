from image2ascii.plugin import BasePlugin
from image2ascii_emoji.cli import EmojiListSubCommand, EmojiSubCommand
from image2ascii_emoji.functions import completer


class Plugin(BasePlugin):
    cli_subcommands = {"emoji": EmojiSubCommand, "emoji-list": EmojiListSubCommand}
    completers = {"emoji.term": completer}
