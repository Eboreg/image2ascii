import re
from collections import namedtuple
from statistics import mean
from typing import List, Optional

from colorama import Fore, ansi

from image2ascii import EMPTY_CHARACTER

ANSI_COLOR_PATTERN = re.escape(ansi.CSI) + r"\d+m"
EMPTY_ROW_PATTERN = re.compile(rf"^{EMPTY_CHARACTER}*({ANSI_COLOR_PATTERN})?{EMPTY_CHARACTER}*$")

RGB = namedtuple("RGB", ["red", "green", "blue"])


class Color:
    name: Optional[str]

    def __init__(self, rgb: RGB, ansi: str):
        self.ansi = ansi
        self.rgb = rgb
        self.name = None

    def __repr__(self):
        if self.name is not None:
            return self.name
        return super().__repr__()

    @property
    def hex(self) -> str:
        return "#{:02x}{:02x}{:02x}".format(self.rgb.red, self.rgb.green, self.rgb.blue)

    def compare(self, other: RGB) -> float:
        """1.0 = perfect match, 0.0 = complete opposite"""
        diffs = [abs(other[idx] - self.rgb[idx]) for idx in range(3)]
        return 1 - mean(diffs) / 0xff

    def set_name(self, name: str):
        self.name = name


class ColorConverter:
    BLACK = Color(RGB(0x00, 0x00, 0x00), Fore.BLACK)
    BLUE = Color(RGB(0x00, 0x00, 0x80), Fore.BLUE)
    GREEN = Color(RGB(0x00, 0x80, 0x00), Fore.GREEN)
    CYAN = Color(RGB(0x00, 0x80, 0x80), Fore.CYAN)
    RED = Color(RGB(0x80, 0x00, 0x00), Fore.RED)
    MAGENTA = Color(RGB(0x80, 0x00, 0x80), Fore.MAGENTA)
    YELLOW = Color(RGB(0x80, 0x80, 0x00), Fore.YELLOW)
    WHITE = Color(RGB(0xc0, 0xc0, 0xc0), Fore.WHITE)

    LIGHTBLACK = Color(RGB(0x40, 0x40, 0x40), Fore.LIGHTBLACK_EX)
    LIGHTBLUE = Color(RGB(0x00, 0x00, 0xff), Fore.LIGHTBLUE_EX)
    LIGHTGREEN = Color(RGB(0x00, 0xff, 0x00), Fore.LIGHTGREEN_EX)
    LIGHTCYAN = Color(RGB(0x00, 0xff, 0xff), Fore.LIGHTCYAN_EX)
    LIGHTRED = Color(RGB(0xff, 0x00, 0x00), Fore.LIGHTRED_EX)
    LIGHTMAGENTA = Color(RGB(0xff, 0x00, 0xff), Fore.LIGHTMAGENTA_EX)
    LIGHTYELLOW = Color(RGB(0xff, 0xff, 0x00), Fore.LIGHTYELLOW_EX)
    LIGHTWHITE = Color(RGB(0xff, 0xff, 0xff), Fore.LIGHTWHITE_EX)

    def __init__(self):
        self.colors: List[Color] = []
        for attr_name in self.__dir__():
            if not attr_name.startswith("_"):
                attr = getattr(self, attr_name)
                if isinstance(attr, Color):
                    attr.set_name(attr_name)
                    self.colors.append(attr)

    def from_rgb(self, rgb: RGB) -> Color:
        diffs = [(ansi, ansi.compare(rgb)) for ansi in self.colors]
        most_likely = max(diffs, key=lambda d: d[1])[0]
        return most_likely


class ColorConverterInvertBW(ColorConverter):
    BLACK = Color(RGB(0xff, 0xff, 0xff), Fore.BLACK)
    WHITE = Color(RGB(0x40, 0x40, 0x40), Fore.WHITE)
    LIGHTBLACK = Color(RGB(0xc0, 0xc0, 0xc0), Fore.LIGHTBLACK_EX)
    LIGHTWHITE = Color(RGB(0x00, 0x00, 0x00), Fore.LIGHTWHITE_EX)
