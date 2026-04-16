import dataclasses
import re
from os import PathLike
from pathlib import Path

import requests


EMOJI_TEST_URL = "https://www.unicode.org/Public/UCD/latest/emoji/emoji-test.txt"
EMOJI_JSON_URL = "https://github.com/googlefonts/emoji-metadata/blob/main/emoji_17_0_ordering.json"


@dataclasses.dataclass
class Emoji:
    name: str
    codepoints: list[int]
    status: str = ""
    svg: str = ""
    ucd_version: str = ""
    is_flag: bool = False
    animated: bool = False
    directional: bool = False
    tone_group: int = 0
    shortcodes: list[str] = dataclasses.field(default_factory=list)
    alternates: list["Emoji"] = dataclasses.field(default_factory=list)
    emoticons: list[str] = dataclasses.field(default_factory=list)

    @property
    def svg_filename(self):
        codepoints = [f"{cp:04x}" for cp in self.codepoints]
        return "emoji_u" + "_".join(codepoints) + ".svg"

    @property
    def flag_filename(self):
        if region_code := self.region_code:
            return f"{region_code}.svg"
        return None

    @property
    def all_emojis(self) -> list["Emoji"]:
        return [self, *self.alternates]

    @property
    def region_code(self):
        if len(self.codepoints) == 2:
            try:
                return "".join(chr(cp - 0x1f1e6 + ord("A")) for cp in self.codepoints)
            except Exception:
                return None

        # 0x1f3f4 = 127988 = indikerar att detta är regionflagga m bindestreck
        # 917607 = "G"
        # 0xe007f = 917631 = avslutar alltid sådana av ngn orsak
        if len(self.codepoints) >= 6 and self.codepoints[0] == 0x1f3f4 and self.codepoints[-1] == 0xe007f:
            code = "".join(chr(i - 0xe0020) for i in self.codepoints[1:-1])
            return f"{code[:2]}-{code[2:]}"

        return None

    def find_svg(self, svg_dir: Path, flag_dir: Path) -> Path | None:
        if (svg_path := svg_dir / self.svg_filename).exists():
            self.is_flag = False
            self.svg = self.svg_filename
            return svg_path

        if flag_filename := self.flag_filename:
            if (flag_path := flag_dir / flag_filename).exists():
                self.is_flag = True
                self.svg = flag_filename
                return flag_path

        return None

    def to_dict(self):
        return {
            "name": self.name,
            "codepoints": self.codepoints,
            "status": self.status,
            "svg": self.svg,
            "ucd_version": self.ucd_version,
            "is_flag": self.is_flag,
            "tone_group": self.tone_group,
            "shortcodes": self.shortcodes,
            "emoticons": self.emoticons,
            "alternates": [a.to_dict() for a in self.alternates],
        }


@dataclasses.dataclass
class EmojiSubgroup:
    name: str
    emojis: list["Emoji"] = dataclasses.field(default_factory=list)

    @property
    def all_emojis(self) -> list["Emoji"]:
        return [emoji for e in self.emojis for emoji in e.all_emojis]

    def to_dict(self):
        return {"name": self.name, "emojis": [e.to_dict() for e in self.emojis]}


@dataclasses.dataclass
class EmojiGroup:
    name: str
    subgroups: list["EmojiSubgroup"] = dataclasses.field(default_factory=list)

    @property
    def all_emojis(self) -> list["Emoji"]:
        return [emoji for g in self.subgroups for emoji in g.all_emojis]

    def to_dict(self):
        return {"name": self.name, "subgroups": [g.to_dict() for g in self.subgroups]}


def find_emoji(emojis: list["Emoji"], codepoints: list[int]):
    for emoji in emojis:
        if emoji.codepoints == codepoints:
            return emoji
    return None


def read_emoji_test_txt(svg_dir: PathLike | str, flag_dir: PathLike | str, url: str = EMOJI_TEST_URL):
    svg_dir = Path(svg_dir)
    flag_dir = Path(flag_dir)
    emoji_re = re.compile(r"^(?P<codepoints>.*?) *; (?P<status>.*?) *# (?:.*?) (?P<ucd_version>.*?) (?P<name>.*)$")
    group: EmojiGroup | None = None
    subgroup: EmojiSubgroup | None = None
    groups: list[EmojiGroup] = []

    response = requests.get(url, timeout=10)
    response.raise_for_status()

    for line in response.text.split("\n"):
        line = line.strip()
        if line.startswith("# group: "):
            group = EmojiGroup(name=line[9:])
            groups.append(group)

        elif group and line.startswith("# subgroup: "):
            subgroup = EmojiSubgroup(name=line[12:])
            group.subgroups.append(subgroup)

        elif subgroup:
            if m := emoji_re.match(line):
                emoji = Emoji(
                    name=m.group("name"),
                    codepoints=[int(cp, base=16) for cp in m.group("codepoints").lower().split(" ")],
                    status=m.group("status"),
                    ucd_version=m.group("ucd_version"),
                )
                if 0xfe0f not in emoji.codepoints and emoji.find_svg(svg_dir, flag_dir):
                    subgroup.emojis.append(emoji)

    return groups


def update_from_emoji_json(groups: list["EmojiGroup"], url: str = EMOJI_JSON_URL):
    def update_emoji(emoji: "Emoji", json_emoji: dict):
        emoji.shortcodes = json_emoji["shortcodes"].copy()
        emoji.emoticons = json_emoji["emoticons"].copy()
        emoji.tone_group = json_emoji["tone_group"]
        emoji.animated = json_emoji["animated"]
        emoji.directional = json_emoji["directional"]

    response = requests.get(url, timeout=10)
    response.raise_for_status()

    all_emojis = [e for g in groups for e in g.all_emojis]
    to_remove: list[list[int]] = [] # codepoints

    for json_group in response.json():
        for json_emoji in json_group["emoji"]:
            codepoints = json_emoji["base"]
            emoji = find_emoji(all_emojis, codepoints)

            if not emoji:
                continue

            update_emoji(emoji, json_emoji)

            for json_alternate in json_emoji["alternates"]:
                alternate = find_emoji(all_emojis, json_alternate)

                if alternate and alternate.codepoints != emoji.codepoints:
                    update_emoji(alternate, json_emoji)
                    emoji.alternates.append(alternate)
                    to_remove.append(alternate.codepoints)

    for group in groups:
        for subgroup in group.subgroups:
            subgroup.emojis = [e for e in subgroup.emojis if e.codepoints not in to_remove]

    return groups
