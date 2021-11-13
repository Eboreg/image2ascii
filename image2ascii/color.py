import re
from collections import namedtuple
from statistics import mean
from typing import List, Optional

import colorama

from image2ascii import EMPTY_CHARACTER

ANSI_COLOR_PATTERN = re.escape(colorama.ansi.CSI) + r"\d+m"
EMPTY_ROW_PATTERN = re.compile(rf"^{EMPTY_CHARACTER}*({ANSI_COLOR_PATTERN})?{EMPTY_CHARACTER}*$")

Color = namedtuple("Color", ["red", "green", "blue"])


class ANSIColor:
    name: Optional[str]

    def __init__(self, code: str, color: Color):
        self.code = code
        self.color = color
        self.name = None

    def __repr__(self):
        if self.name is not None:
            return self.name
        return super().__repr__()

    def compare(self, other: Color) -> float:
        """1.0 = perfect match, 0.0 = complete opposite"""
        diffs = [abs(other[idx] - self.color[idx]) for idx in range(3)]
        return 1 - mean(diffs) / 0xff

    def set_name(self, name: str):
        self.name = name


class ANSIColorConverter:
    BLACK = ANSIColor(colorama.Fore.BLACK, Color(0x00, 0x00, 0x00))
    BLUE = ANSIColor(colorama.Fore.BLUE, Color(0x00, 0x00, 0x80))
    GREEN = ANSIColor(colorama.Fore.GREEN, Color(0x00, 0x80, 0x00))
    CYAN = ANSIColor(colorama.Fore.CYAN, Color(0x00, 0x80, 0x80))
    RED = ANSIColor(colorama.Fore.RED, Color(0x80, 0x00, 0x00))
    MAGENTA = ANSIColor(colorama.Fore.MAGENTA, Color(0x80, 0x00, 0x80))
    YELLOW = ANSIColor(colorama.Fore.YELLOW, Color(0x80, 0x80, 0x00))
    WHITE = ANSIColor(colorama.Fore.WHITE, Color(0xc0, 0xc0, 0xc0))

    LIGHTBLACK = ANSIColor(colorama.Fore.LIGHTBLACK_EX, Color(0x40, 0x40, 0x40))
    LIGHTBLUE = ANSIColor(colorama.Fore.LIGHTBLUE_EX, Color(0x00, 0x00, 0xff))
    LIGHTGREEN = ANSIColor(colorama.Fore.LIGHTGREEN_EX, Color(0x00, 0xff, 0x00))
    LIGHTCYAN = ANSIColor(colorama.Fore.LIGHTCYAN_EX, Color(0x00, 0xff, 0xff))
    LIGHTRED = ANSIColor(colorama.Fore.LIGHTRED_EX, Color(0xff, 0x00, 0x00))
    LIGHTMAGENTA = ANSIColor(colorama.Fore.LIGHTMAGENTA_EX, Color(0xff, 0x00, 0xff))
    LIGHTYELLOW = ANSIColor(colorama.Fore.LIGHTYELLOW_EX, Color(0xff, 0xff, 0x00))
    LIGHTWHITE = ANSIColor(colorama.Fore.LIGHTWHITE_EX, Color(0xff, 0xff, 0xff))

    def __init__(self):
        self.colors: List[ANSIColor] = []
        for attr_name in self.__dir__():
            if not attr_name.startswith("_"):
                attr = getattr(self, attr_name)
                if isinstance(attr, ANSIColor):
                    attr.set_name(attr_name)
                    self.colors.append(attr)

    def from_rgb(self, color: Color) -> str:
        diffs = [(ansi, ansi.compare(color)) for ansi in self.colors]
        most_likely = max(diffs, key=lambda d: d[1])[0]
        return most_likely.code


class ANSIColorConverterInvertBW(ANSIColorConverter):
    BLACK = ANSIColor(colorama.Fore.BLACK, Color(0xff, 0xff, 0xff))
    WHITE = ANSIColor(colorama.Fore.WHITE, Color(0x40, 0x40, 0x40))
    LIGHTBLACK = ANSIColor(colorama.Fore.LIGHTBLACK_EX, Color(0xc0, 0xc0, 0xc0))
    LIGHTWHITE = ANSIColor(colorama.Fore.LIGHTWHITE_EX, Color(0x00, 0x00, 0x00))
