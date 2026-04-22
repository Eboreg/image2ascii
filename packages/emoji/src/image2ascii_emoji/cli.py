from pathlib import Path

from image2ascii_cli.config import CliConvertSettings, CliFileConvertSettings
from pydantic import AliasChoices, Field
from pydantic_settings import BaseSettings, CliPositionalArg, CliSuppress

from image2ascii.plugin import BaseCliSubCommand
from image2ascii_emoji.constants import EMOJI_SVG_PATH, FLAG_SVG_PATH
from image2ascii_emoji.data import Emoji
from image2ascii_emoji.enums import GenderType, SkinToneType
from image2ascii_emoji.functions import get_emoji_collection_interactive


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
        collection = get_emoji_collection_interactive()
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


class EmojiListSubCommand(BaseCliSubCommand):
    """List all available emojis (long list!)"""
    variations: bool = Field(default=False, description="Include all skintone & gender variations")
    keywords: bool = Field(default=False, description="Also include each emoji's list of keywords")

    def run(self):
        collection = get_emoji_collection_interactive()

        for group_idx, group in enumerate(collection.groups):
            if group_idx > 0:
                print()

            print(f"==[ {group.name.upper()} ]" + ("=" * (82 - len(group.name))))

            for subgroup in group.subgroups:
                print(f"--[ {subgroup.name} ]" + ("-" * (82 - len(subgroup.name))))
                all_emojis = subgroup.all_emojis if self.variations else subgroup.emojis
                max_name_length = max(max(len(e.name) for e in all_emojis), 40) + 2
                max_cli_args_length = max(max(len(e.cli_args) for e in all_emojis), 40) + 2

                for emoji in subgroup.emojis:
                    emoji_row = f"{emoji.name:{max_name_length}s} {emoji.cli_args:{max_cli_args_length}s}"
                    if subgroup.name != "country-flag":
                        emoji_row += f" {emoji.unicode}"
                    print(emoji_row)
                    if self.keywords and emoji.keywords:
                        print("    " + ", ".join(emoji.keywords))

                    if self.variations:
                        for variation in emoji.variations:
                            print(
                                f"  {variation.name:{max_name_length - 2}s} "
                                f"{variation.cli_args:{max_cli_args_length - 2}s} {variation.unicode}"
                            )
