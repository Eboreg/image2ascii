import re
from abc import ABC
from functools import cached_property
from pathlib import Path
from typing import TYPE_CHECKING, Self, cast

import requests
from bs4 import BeautifulSoup, Tag
from pydantic import BaseModel, Field
from unidecode import unidecode

from image2ascii_emoji.constants import EMOJI_LIST_URL, EMOJI_MODIFIER_URL, EMOJI_SVG_PATH, FLAG_SVG_PATH
from image2ascii_emoji.enums import Gender, Hair, SkinTone


if TYPE_CHECKING:
    from image2ascii_emoji.cli import EmojiSearch


GENDER_WORDS = "man|woman|men|women|person|people"
GENDER_RE = re.compile(rf".*?(?<!\w)({GENDER_WORDS})(?:, ({GENDER_WORDS}))?(?!\w).*")
GENDER_CHILD_RE = re.compile(r".*?(?<!\w)(boy|girl)(?:, (boy|girl))?(?!\w).*")
HAIR_RE = re.compile(r".*((red|curly|white|blond)(?= hair)|bald).*")
SKIN_TONE_RE = re.compile(r".*?([^ ]+) skin tone(?:, ([^ ]+) skin tone)?.*")


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
    hair: Hair | None = None

    @cached_property
    def all_names(self) -> list[str]:
        return [self.name]

    @cached_property
    def cli_args(self) -> str:
        return self.slug

    @cached_property
    def emoji_filename(self):
        codes = [cp for cp in self.codes if cp != "fe0f"]
        return "emoji_u" + "_".join(codes) + ".svg"

    @cached_property
    def flag_filename(self):
        if region_code := self.region_code:
            return f"{region_code}.svg"
        return None

    @cached_property
    def formatted_keywords(self):
        return [Emoji.slugify(keyword) for keyword in self.keywords]

    @cached_property
    def formatted_names(self):
        return [Emoji.slugify(name) for name in self.all_names]

    @cached_property
    def is_flag(self) -> bool:
        return self.subgroup_name in ("subdivision-flag", "country-flag")

    @property
    def is_variation(self) -> bool:
        return False

    @cached_property
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

    @property
    def short_name(self):
        return self.name

    @cached_property
    def slug(self):
        return Emoji.slugify(self.get_base_name())

    @cached_property
    def unicode(self):
        codes = [int(code, base=16) for code in self.codes]
        return "".join(chr(code) for code in codes)

    def get_base_name(self) -> str:
        return self.name

    def match(self, search: "EmojiSearch") -> None | EmojiSearchMatch:
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
            (search.facing_right is not None and search.facing_right != self.facing_right) or
            (search.hair and search.hair != self.hair)
        ):
            return None

        if not self.get_path(emoji_dir=search.paths.emoji_dir, flag_dir=search.paths.flag_dir).exists():
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
                search.hair == self.hair,
            ]),
        )

    def get_path(self, emoji_dir: Path = EMOJI_SVG_PATH, flag_dir: Path = FLAG_SVG_PATH) -> Path:
        if self.is_flag:
            if flag_filename := self.flag_filename:
                return flag_dir / flag_filename
        return emoji_dir / self.emoji_filename

    @classmethod
    def create_from_tr(cls, tr: Tag, subgroup: "EmojiSubGroup") -> "EmojiVariation | EmojiBase":
        codes = cast(str, cast(Tag, tr.select_one("td.code a"))["name"]).split("_")
        name_tags = tr.select("td.name")
        name = cls.scrub_name(name_tags[0].text)
        keywords = name_tags[1].text.split(" | ") if len(name_tags) > 1 else []
        parts = re.split(r" *[,:] *", name)
        gender: Gender | None = None
        gender_2: Gender | None = None
        skin_tone: SkinTone | None = None
        skin_tone_2: SkinTone | None = None
        hair: Hair | None = None
        facing_right: bool = False
        base_name = parts.pop(0)
        base_name_alt: str | None = None

        # Match 'kiss: woman, man' but not 'family: man, woman, boy':
        if gender_match := GENDER_RE.match(", ".join(parts)):
            if not GENDER_CHILD_RE.match(", ".join(parts)):
                gender, gender_2 = Gender.validate(gender_match.group(1)), Gender.validate(gender_match.group(2))
                parts = [p for p in parts if not GENDER_RE.match(p)]

        # Match 'woman teacher', 'man farmer: dark skin tone', etc:
        if not gender:
            base_name_split = base_name.split(" ")
            if gender := Gender.validate(base_name_split[0]):
                if len(base_name_split) > 1:
                    base_name_alt = base_name
                    base_name = " ".join(base_name_split[1:])

        if gender and not gender_2:
            gender_2 = gender

        if skin_tone_match := SKIN_TONE_RE.match(", ".join(parts)):
            skin_tone, skin_tone_2 = (
                SkinTone.validate(skin_tone_match.group(1)),
                SkinTone.validate(skin_tone_match.group(2)),
            )
            if skin_tone and not skin_tone_2:
                skin_tone_2 = skin_tone
            parts = [p for p in parts if not SKIN_TONE_RE.match(p)]

        if hair_match := HAIR_RE.match(", ".join(parts)):
            hair = Hair.validate(hair_match.group(1))
            parts = [p for p in parts if not HAIR_RE.match(p)]

        if "facing right" in parts:
            facing_right = True
            parts = [p for p in parts if p != "facing right"]

        if parts:
            base_name += ": " + ", ".join(parts)

        if emoji_base := subgroup.find_emoji_base_by_name([base_name, base_name_alt]):
            variation = EmojiVariation(
                codes=codes,
                name=name,
                keywords=keywords,
                subgroup_name=subgroup.name,
                facing_right=facing_right,
                gender=gender,
                gender_2=gender_2,
                skin_tone=skin_tone,
                skin_tone_2=skin_tone_2,
                hair=hair,
                base_name=base_name,
                base_name_alt=base_name_alt,
                base_gender=emoji_base.gender,
            )
            emoji_base.add_variation(variation)
            return variation

        emoji_base = EmojiBase(
            codes=codes,
            name=name,
            keywords=keywords,
            subgroup_name=subgroup.name,
            facing_right=facing_right,
            gender=gender,
            gender_2=gender_2,
            skin_tone=skin_tone,
            skin_tone_2=skin_tone_2,
            hair=hair,
        )
        subgroup.emojis.append(emoji_base)
        return emoji_base

    @staticmethod
    def slugify(name: str):
        name  = re.sub(r"[:,“”’⊛().&!]+", "", name.lower())
        name = name.replace(" - ", "-").strip("-").strip(" ")
        name = unidecode(name)
        return re.sub(r" +", "-", name)

    @staticmethod
    def scrub_name(name: str):
        return re.sub(r"⊛ *", "", name)


class EmojiVariation(Emoji):
    base_name: str = ""
    base_name_alt: str | None = None
    base_gender: Gender | None = None

    @cached_property
    def all_names(self) -> list[str]:
        return [self.name, self.base_name]

    @cached_property
    def cli_args(self) -> str:
        args = [self.slug]
        if self.facing_right:
            args.append("--facing-right")
        if self.gender and self.gender != self.base_gender:
            args.append(f"--gender {self.gender}")
        if self.gender_2 and self.gender_2 != self.gender:
            args.append(f"--gender2 {self.gender_2}")
        if self.skin_tone:
            args.append(f"--skin {self.skin_tone}")
        if self.skin_tone_2 and self.skin_tone_2 != self.skin_tone:
            args.append(f"--skin2 {self.skin_tone_2}")
        if self.hair:
            args.append(f"--hair {self.hair}")
        return " ".join(args)

    @property
    def is_variation(self) -> bool:
        return True

    @property
    def short_name(self):
        return self.name.replace(f"{self.base_name}: ", "")

    def get_base_name(self) -> str:
        return self.base_name


class EmojiBase(Emoji):
    variations: list[EmojiVariation] = Field(default_factory=list, repr=False)

    @cached_property
    def all_emojis(self) -> list[Emoji]:
        return [self, *self.variations]

    def add_variation(self, variation: EmojiVariation):
        if variation.base_name_alt and variation.base_name_alt.lower() == self.name.lower():
            variation.base_name = variation.base_name_alt
        variation.base_gender = self.gender
        self.variations.append(variation)


class EmojiSubGroup(BaseModel):
    name: str = ""
    emojis: list[EmojiBase] = Field(default_factory=list, repr=False)

    @cached_property
    def all_emojis(self) -> list[Emoji]:
        return [emoji for emoji_base in self.emojis for emoji in emoji_base.all_emojis]

    def find_emoji_base_by_name(self, names: list[str | None]) -> EmojiBase | None:
        names = [name.lower() for name in names if name is not None]
        for emoji_base in self.emojis:
            if emoji_base.name.lower() in names:
                return emoji_base
        return None


class EmojiGroup(BaseModel):
    name: str = ""
    subgroups: list[EmojiSubGroup] = Field(default_factory=list, repr=False)

    @cached_property
    def all_emojis(self) -> list[Emoji]:
        return [e for sg in self.subgroups for e in sg.all_emojis]

    def find_subgroup(self, name: str) -> EmojiSubGroup | None:
        for subgroup in self.subgroups:
            if subgroup.name == name:
                return subgroup
        return None


class EmojiCollection(BaseModel):
    groups: list[EmojiGroup] = Field(default_factory=list)

    @cached_property
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
                Emoji.create_from_tr(tr, subgroup)

    def search(self, search: "EmojiSearch") -> list[Emoji]:
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
        collection = cls.scrape_emoji_list(url=list_url)
        collection.scrape_emoji_modifiers(url=modifiers_url)

        return collection

    @classmethod
    def scrape_emoji_list(cls, url: str = EMOJI_LIST_URL) -> Self:
        response = requests.get(url, timeout=20)
        soup = BeautifulSoup(response.text, "html.parser")
        subgroup = EmojiSubGroup()
        group = EmojiGroup(subgroups=[subgroup])
        groups: list[EmojiGroup] = [group]

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
                Emoji.create_from_tr(tr, subgroup)

        return cls(groups=groups)
