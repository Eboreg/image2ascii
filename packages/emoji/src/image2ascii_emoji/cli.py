from pathlib import Path

from image2ascii_cli.config import CliConvertSettings, CliFileConvertSettings
from pydantic import AliasChoices, Field
from pydantic_settings import BaseSettings, CliPositionalArg, CliSuppress

from image2ascii.plugin import BaseCliSubCommand
from image2ascii_emoji.constants import (
    EMOJI_LIST_URL,
    EMOJI_MODIFIER_URL,
    EMOJI_SVG_PATH,
    FLAG_SVG_PATH,
    USER_DATA_PATH,
)
from image2ascii_emoji.data import Emoji
from image2ascii_emoji.enums import GenderType, SkinToneType
from image2ascii_emoji.functions import (
    download_svgs,
    get_emoji_collection,
    is_svg_download_needed,
    reload_emoji_collection,
)


class EmojiSearch(BaseSettings):
    term: CliPositionalArg[str]
    all: bool = Field(default=False, description="List all matching emojis instead of just using the best match")
    facing_right: bool | None = Field(default=None, description="Some emojis have special 'facing right' variations")
    gender: GenderType | None = None
    gender_2: GenderType | None = Field(
        default=None,
        validation_alias=AliasChoices("gender2", "gender-2"),
        description="Gender of the 2nd person in the image, if any. Defaults to same as `gender` if not specified.",
    )
    skin_tone: SkinToneType | None = Field(default=None, validation_alias=AliasChoices("skin", "skin-tone"))
    skin_tone_2: SkinToneType | None = Field(
        default=None,
        validation_alias=AliasChoices("skin2", "skin-tone-2"),
        description=(
            "Skin tone of the 2nd person in the image, if any. Defaults to same as `skin-tone` if not specified."
        ),
    )
    emoji_dir: Path = Field(default=EMOJI_SVG_PATH, description="Path to emoji SVG files")
    flag_dir: Path = Field(default=FLAG_SVG_PATH, description="Path to flag SVG files")
    check_svg: CliSuppress[bool] = True

    @property
    def formatted_term(self):
        return Emoji.clean_name(self.term).replace("-", " ")


class EmojiSubCommand(EmojiSearch, CliConvertSettings, BaseCliSubCommand, extra="ignore"):
    """All your favourites."""
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
            file_convert_settings = CliFileConvertSettings(filename=str(svg_path), **self.model_dump())
            file_convert_settings.run()

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
