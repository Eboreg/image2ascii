import enum
import re
from abc import ABC
from pathlib import Path
from typing import Annotated, Any, Self, cast

import requests
from bs4 import BeautifulSoup, Tag
from pydantic import AliasChoices, BaseModel, BeforeValidator, Field
from pydantic_settings import CliPositionalArg, CliSuppress

from image2ascii.utils import split_list
from image2ascii_emoji.constants import EMOJI_LIST_URL, EMOJI_MODIFIER_URL, EMOJI_SVG_PATH, FLAG_SVG_PATH


SKIN_TONE_RE = re.compile(r".*?([^ ]+) skin tone(?:, ([^ ]+) skin tone)?.*")


class Gender(enum.StrEnum):
    FEMALE = "female"
    MALE = "male"

    @staticmethod
    def validate_gender(value: str) -> "Gender | None":
        value = value.upper()
        if value in Gender.__members__:
            return Gender[value]
        if value in Gender:
            return Gender(value)
        return None


class SkinTone(enum.StrEnum):
    LIGHT = "light"
    MEDIUM_LIGHT = "medium-light"
    MEDIUM = "medium"
    MEDIUM_DARK = "medium-dark"
    DARK = "dark"

    @classmethod
    def get(cls, v: Any) -> Self | None:
        if v in cls:
            return cls(v)
        return None

    @staticmethod
    def validate_skin_tone(value: str) -> "SkinTone | None":
        value = value.upper().replace("-", "_")
        if value in SkinTone.__members__:
            return SkinTone[value]
        if value in SkinTone:
            return SkinTone(value)
        return None


GenderType = Annotated[Gender, BeforeValidator(Gender.validate_gender)]

SkinToneType = Annotated[SkinTone, BeforeValidator(SkinTone.validate_skin_tone)]


class EmojiSearch(BaseModel):
    term: CliPositionalArg[str]
    all: bool = Field(default=False, description="List all matches instead of just using the best one")
    facing_right: bool | None = None
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
    emoji_dir: Path = EMOJI_SVG_PATH
    flag_dir: Path = FLAG_SVG_PATH
    check_svg: CliSuppress[bool] = True

    @property
    def formatted_term(self):
        return Emoji.clean_name(self.term).replace("-", " ")


class EmojiSearchMatch(BaseModel):
    emoji: "Emoji"
    matches_name_exactly: bool
    matches_name: bool
    matches_keywords_exactly: bool
    matches_keywords: bool
    variation_matches: int

    @property
    def points(self):
        return sum([
            10 if self.matches_name_exactly else 0,
            self.matches_name,
            5 if self.matches_keywords_exactly else 0,
            self.matches_keywords,
            self.variation_matches,
        ])


class Emoji(BaseModel, ABC):
    codes: list[str]
    name: str
    keywords: list[str]
    subgroup_name: str
    facing_right: bool = False
    gender: Gender | None = None
    gender_2: Gender | None = None
    skin_tone: SkinTone | None = None
    skin_tone_2: SkinTone | None = None

    @property
    def all_names(self) -> list[str]:
        return [self.name]

    @property
    def cli_args(self) -> str:
        args = [Emoji.clean_name(self.get_base_name()).replace(" ", "-")]
        if self.facing_right:
            args.append("--facing-right")
        if self.gender:
            args.append(f"--gender {self.gender}")
        if self.gender_2 and self.gender_2 != self.gender:
            args.append(f"--gender2 {self.gender_2}")
        if self.skin_tone:
            args.append(f"--skin {self.skin_tone}")
        if self.skin_tone_2 and self.skin_tone_2 != self.skin_tone:
            args.append(f"--skin2 {self.skin_tone_2}")
        return " ".join(args)

    @property
    def emoji_filename(self):
        codes = [cp for cp in self.codes if cp != "fe0f"]
        return "emoji_u" + "_".join(codes) + ".svg"

    @property
    def flag_filename(self):
        if region_code := self.region_code:
            return f"{region_code}.svg"
        return None

    @property
    def formatted_keywords(self):
        return [Emoji.clean_name(keyword).replace("-", " ") for keyword in self.keywords]

    @property
    def formatted_names(self):
        return [Emoji.clean_name(name).replace("-", " ") for name in self.all_names]

    @property
    def is_flag(self) -> bool:
        return self.subgroup_name in ("subdivision-flag", "country-flag")

    @property
    def is_variation(self) -> bool:
        return False

    @property
    def region_code(self) -> str | None:
        try:
            if len(self.codes) == 2:
                return "".join(chr(int(code, base=16) - 0x1F1E6 + ord("A")) for code in self.codes)
            # 0x1f3f4 = 127988 = indicates that this is a regional flag with a dash
            # 0xe007f = 917631 = always finishes such codepoints for some reason
            if len(self.codes) >= 6 and self.codes[0] == "1f3f4" and self.codes[-1] == "e007f":
                code = "".join(chr(int(c, base=16) - 0xE0020) for c in self.codes[1:-1])
                return f"{code[:2]}-{code[2:]}"
        except Exception:
            pass
        return None

    def get_base_name(self) -> str:
        return self.name

    def likeness(self, other: "Emoji") -> int:
        return sum([
            self.facing_right == other.facing_right,
            self.gender == other.gender,
            self.gender_2 == other.gender_2,
            self.skin_tone == other.skin_tone,
            self.skin_tone_2 == other.skin_tone_2,
        ])

    def match(self, search: EmojiSearch) -> None | EmojiSearchMatch:
        if (
            not any(search.formatted_term in name for name in self.formatted_names) and
            not any(search.formatted_term in keyword for keyword in self.formatted_keywords)
        ):
            return None

        gender_2 = search.gender_2 or search.gender
        skin_tone_2 = search.skin_tone_2 or search.skin_tone

        if (
            (search.gender and search.gender != self.gender) or
            (gender_2 and gender_2 != self.gender_2) or
            (search.skin_tone and search.skin_tone != self.skin_tone) or
            (skin_tone_2 and skin_tone_2 != self.skin_tone_2) or
            (search.facing_right is not None and search.facing_right != self.facing_right)
        ):
            return None

        if search.check_svg and not self.svg_path(emoji_dir=search.emoji_dir, flag_dir=search.flag_dir).exists():
            return None

        return EmojiSearchMatch(
            emoji=self,
            matches_name_exactly=any(search.formatted_term == name for name in self.formatted_names),
            matches_name=any(search.formatted_term in name for name in self.formatted_names),
            matches_keywords_exactly=any(search.formatted_term == keyword for keyword in self.formatted_keywords),
            matches_keywords=any(search.formatted_term in keyword for keyword in self.formatted_keywords),
            variation_matches=sum([
                self.facing_right == (search.facing_right or False),
                search.gender == self.gender,
                gender_2 == self.gender_2,
                search.skin_tone == self.skin_tone,
                skin_tone_2 == self.skin_tone_2,
            ]),
        )

    def svg_path(self, emoji_dir: Path = EMOJI_SVG_PATH, flag_dir: Path = FLAG_SVG_PATH) -> Path:
        if self.is_flag:
            if flag_filename := self.flag_filename:
                return flag_dir / flag_filename
        return emoji_dir / self.emoji_filename

    @staticmethod
    def clean_name(name: str):
        name  = re.sub(r"[:,“”’⊛]+", "", name.lower()).strip("-").strip(" ")
        return name

    @staticmethod
    def remove_genders_from_name(name: str):
        name = re.sub(r"^(?:man )|(?:woman )(.*$)", r"\1", name)
        if ": " in name:
            colon_separated = name.rsplit(": ", maxsplit=1)
            after_colon = colon_separated[-1].split(", ")
            if all(a in ("woman", "man") for a in after_colon):
                name = colon_separated[0]
        return name


class EmojiVariation(Emoji):
    base_name: str

    @property
    def all_names(self) -> list[str]:
        return [self.name, self.base_name]

    @property
    def is_variation(self) -> bool:
        return True

    def get_base_name(self) -> str:
        return self.base_name


class EmojiBase(Emoji):
    variations: list[EmojiVariation] = Field(default_factory=list, repr=False)

    @property
    def all_emojis(self) -> list[Emoji]:
        return [self, *self.variations]

    def best_matching_variation(self, other: Emoji) -> Emoji:
        results = [(e, e.likeness(other)) for e in self.all_emojis]
        return sorted(results, key=lambda t: t[1], reverse=True)[0][0]

    def is_base_of(self, name: str, codes: list[str]) -> bool:
        if Emoji.remove_genders_from_name(name) == self.name:
            return True

        if len(codes) <= len(self.codes):
            return False

        if len(codes) >= len(self.codes) and codes[: len(self.codes)] == self.codes:
            return True

        split_codes = split_list(codes, ["200d", "fe0f"])
        split_own_codes = split_list(self.codes, ["200d", "feof"])

        return any(c in split_own_codes for c in split_codes)

    def variation_from_scraped_tr(self, tr: Tag, subgroup_name: str) -> bool:
        codes = cast(str, cast(Tag, tr.select_one("td.code a"))["name"]).split("_")
        name_tags = tr.select("td.name")
        name: str = name_tags[0].text
        keywords: list[str] = name_tags[1].text.split(" | ") if len(name_tags) > 1 else []

        if self.is_base_of(name, codes):
            facing_right = "facing right" in name

            gender: Gender | None = None
            gender_2: Gender | None = None
            person1_male = (
                ("man" in name and name.replace("man", "person").startswith(self.name))
                or ("men" in name and name.replace("men", "people").startswith(self.name))
                or name == f"{self.name}: man, man"
                or ("person" in self.keywords and "man" in keywords and "woman" not in keywords)
                or ("people" in self.keywords and "men" in keywords)
            )
            person1_female = (
                ("woman" in name and name.replace("woman", "person").startswith(self.name))
                or ("women" in name and name.replace("women", "people").startswith(self.name))
                or ("woman and man" in name and name.replace("woman and man", "people").startswith(self.name))
                or name == f"{self.name}: woman, woman"
                or name == f"{self.name}: woman, man"
                or ("person" in self.keywords and "woman" in keywords)
                or ("people" in self.keywords and "women" in keywords)
            )
            person2_male = (person1_female or person1_male) and (
                ("woman and man" in name and name.replace("woman and man", "people").startswith(self.name))
                or ("men" in name and name.replace("men", "people").startswith(self.name))
                or name == f"{self.name}: woman, man"
                or name == f"{self.name}: man, man"
                or ("people" in self.keywords and "men" in keywords)
            )
            person2_female = (person1_female or person1_male) and (
                ("women" in name and name.replace("women", "people").startswith(self.name))
                or name == f"{self.name}: woman, woman"
                or ("people" in self.keywords and "women" in keywords)
            )
            if person1_female:
                gender = Gender.FEMALE
            elif person1_male:
                gender = Gender.MALE

            if person2_female:
                gender_2 = Gender.FEMALE
            elif person2_male:
                gender_2 = Gender.MALE
            else:
                gender_2 = gender

            skin_tone: SkinTone | None = None
            skin_tone_2: SkinTone | None = None
            if skin_tone_match := SKIN_TONE_RE.match(name):
                skin_tone, skin_tone_2 = [SkinTone.get(g) for g in skin_tone_match.groups()]
            skin_tone_2 = skin_tone_2 or skin_tone

            if facing_right or gender is not None or skin_tone is not None:
                emoji = EmojiVariation(
                    base_name=self.name,
                    codes=codes,
                    facing_right=facing_right,
                    gender=gender,
                    gender_2=gender_2,
                    keywords=keywords,
                    name=name,
                    skin_tone=skin_tone,
                    skin_tone_2=skin_tone_2,
                    subgroup_name=subgroup_name,
                )
                if not emoji.keywords:
                    # Must be done before adding emoji to self.variations!
                    best_match = self.best_matching_variation(emoji)
                    emoji.keywords = best_match.keywords.copy()
                self.variations.append(emoji)

                return True

        return False

    @classmethod
    def create_from_scraped_tr(cls, tr: Tag, subgroup: "EmojiSubGroup") -> Self:
        codes = cast(str, cast(Tag, tr.select_one("td.code a"))["name"]).split("_")
        name_tags = tr.select("td.name")
        name: str = name_tags[0].text
        keywords: list[str] = name_tags[1].text.split(" | ") if len(name_tags) > 1 else []

        return cls(codes=codes, name=name, keywords=keywords, subgroup_name=subgroup.name)


class EmojiSubGroup(BaseModel):
    name: str = ""
    emojis: list[EmojiBase] = Field(default_factory=list, repr=False)

    @property
    def all_emojis(self) -> list[Emoji]:
        return [e for ewv in self.emojis for e in ewv.all_emojis]

    def find_base_emoji(self, name: str, codes: list[str]) -> EmojiBase | None:
        for emoji in self.emojis:
            if emoji.is_base_of(name, codes):
                return emoji
        return None


class EmojiGroup(BaseModel):
    name: str = ""
    subgroups: list[EmojiSubGroup] = Field(default_factory=list, repr=False)

    @property
    def all_emojis(self) -> list[Emoji]:
        return [e for sg in self.subgroups for e in sg.all_emojis]

    def find_subgroup(self, name: str) -> EmojiSubGroup | None:
        for subgroup in self.subgroups:
            if subgroup.name == name:
                return subgroup
        return None


class EmojiCollection(BaseModel):
    groups: list[EmojiGroup] = Field(default_factory=list)

    @property
    def all_emojis(self) -> list[Emoji]:
        return [e for g in self.groups for e in g.all_emojis]

    def find_group(self, name: str) -> EmojiGroup | None:
        for group in self.groups:
            if group.name == name:
                return group
        return None

    def scrape_emoji_modifiers(self, url: str = EMOJI_MODIFIER_URL):
        # Make sure scrape_emoji_list() has been run first.
        response = requests.get(url, timeout=20)
        soup = BeautifulSoup(response.text, "html.parser")
        group: EmojiGroup | None = None
        subgroup: EmojiSubGroup | None = None

        for tr in soup.select("table tr"):
            if bighead := tr.select_one("th.bighead"):
                group = self.find_group(bighead.text)

            elif mediumhead := tr.select_one("th.mediumhead"):
                if group:
                    subgroup = group.find_subgroup(mediumhead.text)

            elif subgroup and tr.find("td"):
                codes = cast(str, cast(Tag, tr.select_one("td.code a"))["name"]).split("_")
                name_tags = tr.select("td.name")
                name: str = name_tags[0].text
                if base_emoji := subgroup.find_base_emoji(name, codes):
                    base_emoji.variation_from_scraped_tr(tr, subgroup_name=subgroup.name)

    def search(self, search: EmojiSearch) -> list[Emoji]:
        matches = [emoji.match(search) for emoji in self.all_emojis]
        matches = [m for m in matches if m is not None]
        matches = sorted(matches, key=lambda m: m.points, reverse=True)

        exact_matches = [m for m in matches if m.matches_name_exactly]

        if exact_matches and not search.all:
            matches = exact_matches

        if variation_matches := [m for m in matches if m.variation_matches > 0]:
            matches = variation_matches
            if len(matches) > 1:
                if matches[0].variation_matches > matches[1].variation_matches and not search.all:
                    matches = matches[:1]
        elif exact_matches and not search.all:
            if base_matches := [m for m in matches if not m.emoji.is_variation]:
                matches = base_matches

        return [m.emoji for m in matches]

    @classmethod
    def scrape(cls, list_url: str = EMOJI_LIST_URL, modifiers_url: str = EMOJI_MODIFIER_URL) -> Self:
        collection = cls.scrape_emoji_list(list_url)
        collection.scrape_emoji_modifiers(modifiers_url)

        return collection

    @classmethod
    def scrape_emoji_list(cls, url: str = EMOJI_LIST_URL) -> Self:
        response = requests.get(url, timeout=20)
        soup = BeautifulSoup(response.text, "html.parser")
        subgroup = EmojiSubGroup()
        group = EmojiGroup(subgroups=[subgroup])
        groups: list[EmojiGroup] = [group]
        base_emoji: EmojiBase | None = None

        for tr in soup.select("table tr"):
            if bighead := tr.select_one("th.bighead"):
                if group.name:
                    group = EmojiGroup()
                    groups.append(group)
                group.name = bighead.text

            elif mediumhead := tr.select_one("th.mediumhead"):
                if subgroup.name:
                    subgroup = EmojiSubGroup()
                    group.subgroups.append(subgroup)
                subgroup.name = mediumhead.text

            elif tr.find("td"):
                if not base_emoji or not base_emoji.variation_from_scraped_tr(tr, subgroup_name=subgroup.name):
                    base_emoji = EmojiBase.create_from_scraped_tr(tr, subgroup)
                    subgroup.emojis.append(base_emoji)

        return cls(groups=groups)
