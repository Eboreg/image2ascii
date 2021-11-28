from typing import Optional

import numpy as np
from colorama import Fore

from image2ascii.utils import timer

R, G, B = range(3)


@timer
def rgb_to_hsv(rgb: np.ndarray) -> np.ndarray:
    """
    Not used right now, but pretty neat to have, I guess.

    :param rgb: An N-d array, where the innermost one has exactly 3 positions
        (R, G, B).
    :returns: Array with the same shape as `rgb`, but populated with H, S, V
        values.
    """
    axis = len(rgb.shape) - 1

    # Shift the RGB values in each row to put the highest one first, then tack
    # on the peak-to-peak (max - min) value last for efficiency:
    rgbc = np.stack([
        rgb.max(axis=axis),
        np.take_along_axis(rgb, np.expand_dims((rgb.argmax(axis=axis) + 1) % 3, axis=axis), axis=axis).squeeze(),
        np.take_along_axis(rgb, np.expand_dims((rgb.argmax(axis=axis) + 2) % 3, axis=axis), axis=axis).squeeze(),
        rgb.ptp(axis=axis)
    ], axis=axis)

    # HSV values are computed with simplified versions of the methods here:
    # https://math.stackexchange.com/questions/556341/rgb-to-hsv-color-conversion-algorithm

    # More precisely: For hue, we take advantage of the fact that we, instead
    # of "manually" checking which colour has the highest value ("0 if M = r"
    # etc), can just multiply its position in the original RGB array by 2 to
    # get the first term of h'. Thanks to this, and to having shifted the RGB
    # values above, we don't need to do change the algorithm depending on
    # which RGB value is the largest ("B - G if M = r" etc).

    # We also simplify parts of the h' calculation; e.g., "(M-b)/c - (M-g)/c"
    # becomes "(g-b)/c". I am bad at math, so shouts out to this excellent
    # tool: https://www.symbolab.com/solver/simplify-calculator
    return np.stack([
        # Hue:
        (
            rgb.argmax(axis=axis) * 2 +
            np.divide(
                rgbc.take(1, axis=axis) - rgbc.take(2, axis=axis),
                rgbc.take(3, axis=axis),
                where=rgbc.take(3, axis=axis) > 0,
                out=np.zeros((*rgb.shape[:-1],))
            )
        ) / 6 % 1 * 360,
        # Saturation:
        np.divide(
            rgbc.take(3, axis=axis),
            rgbc.take(0, axis=axis),
            where=rgbc.take(0, axis=axis) > 0,
            out=np.zeros((*rgb.shape[:-1],))
        ) * 100,
        # Value:
        rgbc.take(0, axis=axis) / 0xff * 100
    ], axis=axis)


def to_css(arr: np.ndarray) -> str:
    return "#{:02x}{:02x}{:02x}".format(arr[R].astype(np.uint8), arr[G].astype(np.uint8), arr[B].astype(np.uint8))


class RGB:
    def __init__(self, red: int, green: int, blue: int):
        self.array = np.array([red, green, blue], dtype=np.uint64)


class Color:
    """
    Really a "colour representation" object. It holds info about a reference
    RGB colour as well as how it should be represented in different formats.
    """
    name: Optional[str]

    def __init__(self, source: RGB, ansi: str):
        """
        :param source: The colour we compare each incoming colour to, i.e.
            if the incoming colour is closer to this colour than to any other,
            this object will be chosen.
        :param ansi: The ANSI code used to render this colour.
        """
        self.source = source
        self.ansi = ansi
        self.css = to_css(source.array)
        self.name = None

    def __repr__(self):
        if self.name is not None:
            return self.name
        return super().__repr__()


BLACK = Color(source=RGB(0x00, 0x00, 0x00), ansi=Fore.BLACK)
BLUE = Color(source=RGB(0x00, 0x00, 0xaa), ansi=Fore.BLUE)
GREEN = Color(source=RGB(0x00, 0xaa, 0x00), ansi=Fore.GREEN)
CYAN = Color(source=RGB(0x00, 0xaa, 0xaa), ansi=Fore.CYAN)
RED = Color(source=RGB(0xaa, 0x00, 0x00), ansi=Fore.RED)
PURPLE = Color(source=RGB(0xaa, 0x00, 0xaa), ansi=Fore.MAGENTA)
BROWN = Color(source=RGB(0xaa, 0x55, 0x00), ansi=Fore.YELLOW)
LIGHTGRAY = Color(source=RGB(0xaa, 0xaa, 0xaa), ansi=Fore.WHITE)

YELLOW = Color(source=RGB(0xff, 0xff, 0x55), ansi=Fore.LIGHTYELLOW_EX)
DARKGRAY = Color(source=RGB(0x55, 0x55, 0x55), ansi=Fore.LIGHTBLACK_EX)
LIGHTBLUE = Color(source=RGB(0x55, 0x55, 0xff), ansi=Fore.LIGHTBLUE_EX)
LIGHTGREEN = Color(source=RGB(0x55, 0xff, 0x55), ansi=Fore.LIGHTGREEN_EX)
LIGHTCYAN = Color(source=RGB(0x55, 0xff, 0xff), ansi=Fore.LIGHTCYAN_EX)
LIGHTRED = Color(source=RGB(0xff, 0x55, 0x55), ansi=Fore.LIGHTRED_EX)
LIGHTPURPLE = Color(source=RGB(0xff, 0x55, 0xff), ansi=Fore.LIGHTMAGENTA_EX)
WHITE = Color(source=RGB(0xff, 0xff, 0xff), ansi=Fore.LIGHTWHITE_EX)


class BaseColorConverter:
    def closest(self, hsv: np.ndarray) -> np.ndarray:
        raise NotImplementedError

    def to_representation(self, array: np.ndarray) -> str:
        raise NotImplementedError


class ANSIColorConverter(BaseColorConverter):
    def __init__(self):
        self.colors = [
            BLACK, BLUE, GREEN, CYAN, RED, PURPLE, BROWN, LIGHTGRAY,
            YELLOW, DARKGRAY, LIGHTBLUE, LIGHTGREEN, LIGHTCYAN, LIGHTRED,
            LIGHTPURPLE, WHITE
        ]
        self.color_matrix = np.array([c.source.array for c in self.colors])

    @timer
    def closest(self, color: np.ndarray) -> np.ndarray:
        """
        For each colour, calculate the difference (as absolute numbers) of
        each parameter with the ones in `array`, and sum these. Then return
        the colour with the least difference.

        Algorithm from:
        https://stackoverflow.com/questions/9018016/how-to-compare-two-colors-for-similarity-difference/9085524#9085524
        """
        rmean = (self.color_matrix[:, R] + color[R]) // 2

        distances = np.sqrt(
            ((512 + rmean) * np.power(self.color_matrix[:, R] - color[R], 2) >> 8) +
            4 * np.power(self.color_matrix[:, G] - color[G], 2) +
            ((767 - rmean) * np.power(self.color_matrix[:, B] - color[B], 2) >> 8)
        )

        return self.colors[np.argmin(distances)].source.array

    @timer
    def to_representation(self, array: np.ndarray) -> str:
        for color in self.colors:
            if np.all(color.source.array == array):
                return color.ansi
        raise ValueError(f"Colour with values {array} not registered")


class HTMLANSIColorConverter(ANSIColorConverter):
    def to_representation(self, array: np.ndarray) -> str:
        for color in self.colors:
            if np.all(color.source.array == array):
                return color.css
        raise ValueError(f"Colour with values {array} not registered")


class HTMLFullRGBColorConverter(BaseColorConverter):
    def closest(self, array: np.ndarray) -> np.ndarray:
        return array

    def to_representation(self, array: np.ndarray) -> str:
        return to_css(array)
