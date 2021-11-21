import re
from typing import List, Optional

import numpy as np
from colorama import Fore, ansi

from image2ascii import EMPTY_CHARACTER
from image2ascii.utils import timer

ANSI_COLOR_PATTERN = re.escape(ansi.CSI) + r"\d+m"
EMPTY_ROW_PATTERN = re.compile(rf"^{EMPTY_CHARACTER}*({ANSI_COLOR_PATTERN})?{EMPTY_CHARACTER}*$")


class RGB:
    def __init__(self, red: int, green: int, blue: int):
        self.red, self.green, self.blue = red, green, blue
        if max(self) > 0:
            self.saturation = (max(self) - min(self)) / (max(self) + min(self)) * 0xff
        else:
            self.saturation = 0.0
        self.array = np.array([self.red, self.green, self.blue, self.saturation])

    def __iter__(self):
        return iter((self.red, self.green, self.blue))

    @property
    def hex(self) -> str:
        return "#{:02x}{:02x}{:02x}".format(self.red, self.green, self.blue)


class Color:
    """
    Really a "colour representation" object. It holds info about a reference
    RGB colour as well as how it should be represented in different formats.
    """
    name: Optional[str]

    def __init__(self, source: RGB, ansi: str, rgb: Optional[RGB] = None):
        """
        :param source: The colour we compare each incoming colour to, i.e.
            if the incoming colour is closer to this colour than to any other,
            this object will be chosen.
        :param ansi: The ANSI code used to render this colour.
        :param rgb: RGB value used to render this colour. Is generally the
            same as `source`, and in that case, it could be omitted.
        """
        self.source = source
        self.ansi = ansi
        self.rgb = rgb or source
        self.name = None

    def __repr__(self):
        if self.name is not None:
            return self.name
        return super().__repr__()

    @property
    def hex(self) -> str:
        return self.rgb.hex


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
                    attr.name = attr_name
                    self.colors.append(attr)
        self.color_matrix = np.array([c.source.array for c in self.colors])

    @timer
    def from_array(self, array: np.ndarray) -> Color:
        """
        For each colour, calculate the difference (as absolute numbers) of
        each parameter with the ones in `array`, and sum these. Then return
        the colour with the least difference.
        """
        diffs = np.absolute(np.subtract(self.color_matrix, array)).sum(axis=1)
        return self.colors[np.argmin(diffs)]


class ColorConverterInvertBW(ColorConverter):
    """Black is rendered as white and vice versa"""
    BLACK = Color(RGB(0xff, 0xff, 0xff), Fore.BLACK, RGB(0x00, 0x00, 0x00))
    WHITE = Color(RGB(0x40, 0x40, 0x40), Fore.WHITE, RGB(0xc0, 0xc0, 0xc0))
    LIGHTBLACK = Color(RGB(0xc0, 0xc0, 0xc0), Fore.LIGHTBLACK_EX, RGB(0x40, 0x40, 0x40))
    LIGHTWHITE = Color(RGB(0x00, 0x00, 0x00), Fore.LIGHTWHITE_EX, RGB(0xff, 0xff, 0xff))
