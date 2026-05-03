from functools import cached_property
from pathlib import Path

from image2ascii_cli.config import CliConvertSettings, CliFileConvertSettings
from pydantic import AliasChoices, Field
from pydantic_settings import (
    BaseSettings,
    CliPositionalArg,
    PydanticBaseSettingsSource,
    YamlConfigSettingsSource,
)

from image2ascii.config import CONFIG_FILE
from image2ascii.plugin import BaseCliSubCommand
from image2ascii_emoji.constants import (
    EMOJI_COLLECTION_PATH,
    EMOJI_LIST_URL,
    EMOJI_MODIFIER_URL,
    EMOJI_SVG_PATH,
    FLAG_SVG_PATH,
)
from image2ascii_emoji.data import Emoji, EmojiCollection
from image2ascii_emoji.enums import GenderType, HairType, SkinToneType
from image2ascii_emoji.functions import download_svgs, get_emoji_collection, reload_emoji_collection


class EmojiPaths(BaseSettings, yaml_file=CONFIG_FILE, yaml_config_section="emoji"):
    emoji_dir: Path = Field(default=EMOJI_SVG_PATH, description="Path to emoji SVG files")
    flag_dir: Path = Field(default=FLAG_SVG_PATH, description="Path to flag SVG files")

    @classmethod
    def settings_customise_sources(
        cls,
        settings_cls: type[BaseSettings],
        init_settings: PydanticBaseSettingsSource,
        env_settings: PydanticBaseSettingsSource,
        dotenv_settings: PydanticBaseSettingsSource,
        file_secret_settings: PydanticBaseSettingsSource,
    ) -> tuple[PydanticBaseSettingsSource, ...]:
        try:
            return init_settings, YamlConfigSettingsSource(settings_cls)
        except KeyError:
            init_settings.config["yaml_config_section"] = None
            init_settings.config["yaml_file"] = None
            return (init_settings,)


class EmojiSearch(BaseSettings):
    term: CliPositionalArg[str] = ""
    all: bool = Field(default=False, description="List all matching emojis instead of just using the best match")
    facing_right: bool | None = Field(default=None, description="Some emojis have special 'facing right' variations")
    gender: GenderType | None = None
    gender_2: GenderType | None = Field(
        default=None,
        validation_alias=AliasChoices("gender2", "gender-2"),
        description="Gender of the 2nd person in the image, if any. Defaults to same as `gender` if not specified.",
    )
    hair: HairType | None = None
    paths: EmojiPaths = Field(default_factory=EmojiPaths)
    skin_tone: SkinToneType | None = Field(default=None, validation_alias=AliasChoices("skin", "skin-tone"))
    skin_tone_2: SkinToneType | None = Field(
        default=None,
        validation_alias=AliasChoices("skin2", "skin-tone-2"),
        description=(
            "Skin tone of the 2nd person in the image, if any. Defaults to same as `skin-tone` if not specified."
        ),
    )

    @cached_property
    def formatted_term(self):
        return Emoji.slugify(self.term)


class BaseEmojiCliSubCommand(BaseCliSubCommand):
    paths: EmojiPaths = Field(default_factory=EmojiPaths)

    def download_callback(self, status: str, br: bool):
        print(status, end="\n" if br else "", flush=True)

    def get_emoji_collection_interactive(self) -> EmojiCollection:
        if self.is_svg_download_needed():
            print("Before you can use image2ascii-emoji, we need to do an automatic one-time download")
            print("of image files from the Noto-Emoji font. The download is ~212 MB, and after extraction")
            print("~63 MB of SVG files will be placed in these locations:")
            print(f" * {self.paths.emoji_dir} (emojis)")
            print(f" * {self.paths.flag_dir} (flags)")
            reply = input("Do this download now? [Y/n] ").strip()
            if not reply or reply in "Yy":
                download_svgs(
                    emoji_dir=self.paths.emoji_dir,
                    flag_dir=self.paths.flag_dir,
                    callback=self.download_callback,
                )

        collection = get_emoji_collection()

        if collection is None:
            print(f"Got to do a one-time scraping of {EMOJI_LIST_URL}")
            print(f"and {EMOJI_MODIFIER_URL},")
            print(f"and compile them into {EMOJI_COLLECTION_PATH}.")
            print("Just a moment ...", end="", flush=True)
            collection = reload_emoji_collection()
            print(" done.")

        return collection

    def is_svg_download_needed(self) -> bool:
        if not self.paths.emoji_dir.exists() or not self.paths.flag_dir.exists():
            return False
        return (
            len(list(self.paths.emoji_dir.glob("*.svg"))) < 3000 or
            len(list(self.paths.flag_dir.glob("*.svg"))) < 300
        )


class EmojiSubCommand(EmojiSearch, CliConvertSettings, BaseEmojiCliSubCommand, extra="ignore"):
    """
    All your favourites, courtesy of the Noto-Emoji font from the good lizard
    people at Google
    """
    redownload: bool = Field(default=False, description="(Re-)download emoji & flag SVG files")
    reload: bool = Field(default=False, description="(Re)load all emoji metadata")

    def run(self):
        if not self.redownload and not self.reload and not self.term:
            print("You have to give me either --redownload, --reload, --help/-h, or a search term.")
        else:
            collection: EmojiCollection | None = None
            if self.redownload:
                print("Will now (re-)download emoji & flag SVG files to these locations:")
                print(f" * {self.paths.emoji_dir} (emojis)")
                print(f" * {self.paths.flag_dir} (flags)")
                download_svgs(
                    emoji_dir=self.paths.emoji_dir,
                    flag_dir=self.paths.flag_dir,
                    callback=self.download_callback,
                )
            if self.reload:
                print(f"Will now scrape {EMOJI_LIST_URL}")
                print(f"and {EMOJI_MODIFIER_URL},")
                print(f"and compile them into {EMOJI_COLLECTION_PATH}.")
                print("Just a moment ...", end="", flush=True)
                collection = reload_emoji_collection()
                print(" done.")
            if self.term:
                self.search_and_convert(collection=collection)

    def search_and_convert(self, collection: EmojiCollection | None = None):
        collection = collection or self.get_emoji_collection_interactive()
        emojis = collection.search(self)

        if len(emojis) == 1:
            svg_path = emojis[0].get_path(emoji_dir=self.paths.emoji_dir, flag_dir=self.paths.flag_dir)
            file_convert_settings = CliFileConvertSettings(path=str(svg_path), **self.model_dump())
            file_convert_settings.run()

        elif len(emojis) > 1:
            name_length = max(max(len(emoji.name) for emoji in emojis) + 2, 40)

            print("Found multiple matches:")
            print()
            print(f"{'NAME':{name_length}s}COMMAND")

            for emoji in emojis:
                print(f"{emoji.name:{name_length}s}i2a emoji {emoji.cli_args}")

        else:
            print("No emojis found.")


class EmojiListSubCommand(BaseEmojiCliSubCommand):
    """List all available emojis (long list; '| less' recommended!)"""
    include_variations: bool = Field(default=False, description="Include all skintone & gender variations")
    include_keywords: bool = Field(default=False, description="Also include each emoji's list of keywords")
    include_paths: bool = Field(default=False, description="Also include full path to SVG files")
    sort: bool = Field(default=False, description="Sort emojis alphabetically in each subgroup")

    def run(self):
        collection = self.get_emoji_collection_interactive()

        for group_idx, group in enumerate(collection.groups):
            if group_idx > 0:
                print()

            print(f"==[ {group.name.upper()} ]" + ("=" * (82 - len(group.name))))

            for subgroup in group.subgroups:
                print(f"--[ {subgroup.name} ]" + ("-" * (82 - len(subgroup.name))))
                all_emojis = subgroup.all_emojis if self.include_variations else subgroup.emojis
                max_name_length = max(max(len(e.short_name) for e in all_emojis), 40) + 2
                max_cli_args_length = max(max(len(e.cli_args) for e in all_emojis), 40) + 2
                emojis = sorted(subgroup.emojis, key=lambda e: e.name.lower()) if self.sort else subgroup.emojis

                for emoji_base in emojis:
                    emoji_row = f"{emoji_base.name:{max_name_length}s} {emoji_base.cli_args:{max_cli_args_length}s}"
                    if subgroup.name != "country-flag":
                        emoji_row += f" {emoji_base.unicode}"
                    print(emoji_row)
                    if self.include_paths:
                        print(f"  {emoji_base.get_path(emoji_dir=self.paths.emoji_dir, flag_dir=self.paths.flag_dir)}")
                    if self.include_keywords and emoji_base.keywords:
                        print("  " + ", ".join(emoji_base.keywords))

                    if self.include_variations:
                        for variation in emoji_base.variations:
                            print(
                                f"  {variation.short_name:{max_name_length - 2}s} "
                                f"{variation.cli_args:{max_cli_args_length}s} {variation.unicode}"
                            )
                            if self.include_paths:
                                path = variation.get_path(emoji_dir=self.paths.emoji_dir, flag_dir=self.paths.flag_dir)
                                print(f"    {path}")
