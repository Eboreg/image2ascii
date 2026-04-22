from image2ascii_cli.config import CliConvertConfig, CliFileConvertConfig

from image2ascii.plugin import BaseCliSubCommand, BasePlugin
from image2ascii_emoji.constants import EMOJI_LIST_URL, EMOJI_MODIFIER_URL, USER_DATA_PATH
from image2ascii_emoji.data import EmojiSearch
from image2ascii_emoji.functions import (
    download_svgs,
    get_emoji_collection,
    is_svg_download_needed,
    reload_emoji_collection,
)


__all__ = ["Plugin"]


class EmojiSubCommand(EmojiSearch, CliConvertConfig, BaseCliSubCommand, extra="ignore"):
    """Sblorg"""
    def run(self):
        if is_svg_download_needed():
            print(
                "Before you can use image2ascii-emoji, we need to do an automatic one-time download \n"
                "of image files from the Noto-Emoji font. The download is ~212 MB, and after extraction \n"
                f"~63 MB of SVG files will be placed under {USER_DATA_PATH}.\n"
            )
            reply = input("Do this download now? [Y/n] ").strip()
            if not reply or reply in "Yy":
                download_svgs(lambda status, br: print(status, end="\n" if br else "", flush=True))

        collection = get_emoji_collection()

        if collection is None:
            print(
                f"Got to do a one-time scraping of {EMOJI_LIST_URL}\n"
                f"and {EMOJI_MODIFIER_URL}.\n"
                "Just a moment ..."
            )
            collection = reload_emoji_collection()

        emojis = collection.search(self)

        if len(emojis) == 1:
            svg_path = emojis[0].svg_path(emoji_dir=self.emoji_dir, flag_dir=self.flag_dir)
            file_convert_config = CliFileConvertConfig(filename=str(svg_path), **self.model_dump())
            file_convert_config.run()

        elif len(emojis) > 1:
            max_length = 100
            name_length = max(max(len(emoji.name) for emoji in emojis[:max_length]) + 2, 40)

            print("Found multiple matches:")
            print()
            print(f"{'NAME':{name_length}s}COMMAND")

            for emoji in emojis[:max_length]:
                print(f"{emoji.name:{name_length}s}i2a emoji {emoji.cli_args}")

            if len(emojis) > max_length:
                print(f"... and {len(emojis) - max_length} more.")

        else:
            print("No emojis found.")


class Plugin(BasePlugin):
    cli_subcommands = {"emoji": EmojiSubCommand}
