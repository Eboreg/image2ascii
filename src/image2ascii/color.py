import re

import numpy as np

from image2ascii.timing import timer
from image2ascii.types import RGBA


# Mnemonics for colour array indices:
# (red, green, blue, alpha, visibility, hue, saturation, value)
# H, S, and Va are currently not used, though.
R, G, B, A, Vi, H, S, Va = range(8)

ANSI_RESET_ALL = "\x1b[0m"
ANSI_RESET_BG = "\x1b[49m"
ANSI_RESET_FG = "\x1b[39m"


class Color:
    array: RGBA

    @property
    def ansi(self) -> str:
        return "\x1b[" + ";".join(self.ansi_codes) + "m"

    @property
    def ansi_background(self) -> str:
        return "\x1b[" + ";".join(self.ansi_codes_background) + "m"

    @property
    def ansi_codes(self) -> list[str]:
        return ["38", "2", str(self.array[R]), str(self.array[G]), str(self.array[B])]

    @property
    def ansi_codes_background(self) -> list[str]:
        return ["48", "2", str(self.array[R]), str(self.array[G]), str(self.array[B])]

    @property
    def css(self) -> str:
        return f"#{self.array[R]:02x}{self.array[G]:02x}{self.array[B]:02x}{self.array[A]:02x}"

    @property
    def rgba_tuple(self) -> tuple[int, ...]:
        return (*self.array.tolist(),)

    @timer
    def __init__(self, array: RGBA):
        self.array = array

    @timer
    def __eq__(self, value: object) -> bool:
        return isinstance(value, Color) and bool(np.all(self.array == value.array))

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}({self.array[R]}, {self.array[G]}, {self.array[B]}, {self.array[A]})"

    def __str__(self) -> str:
        return self.css

    @timer
    def get_distances(
        self,
        colors: np.ndarray[tuple[int, int], np.dtype[np.int64]],
    ) -> np.ndarray[tuple[int], np.dtype[np.float64]]:
        """
        IMPORTANT: Remember to cast colour array to int64 before.
        Max distance between 2 colours seems to be ~764.833. Min is 0.

        Algorithm from:
        https://stackoverflow.com/questions/9018016/how-to-compare-two-colors-for-similarity-difference/9085524#9085524
        """
        rmean = (colors[:, R] + self.array[R]) // 2

        return np.sqrt(
            ((512 + rmean) * np.power(colors[:, R] - self.array[R], 2) >> 8)
            + 4 * np.power(colors[:, G] - self.array[G], 2)
            + ((767 - rmean) * np.power(colors[:, B] - self.array[B], 2) >> 8)
        )

    @timer
    def to_grayscale(self) -> "Color":
        shade = ((self.array[R] * 0.299) + (self.array[G] * 0.587) + (self.array[B] * 0.114)).astype(np.uint8)
        return Color(np.array([shade, shade, shade, self.array[A]]))

    @classmethod
    @timer
    def parse_string(cls, string: str) -> "Color | None":
        """
        Valid input examples:
         - '#321805aa'      => Color(50, 24, 5, 170)
         - '#8812aa'        => Color(136, 18, 170, 255)
         - '#333a'          => Color(51, 51, 51, 170)
         - '#333'           => Color(51, 51, 51, 255)
         - '123456'         => Color(18, 52, 86, 255)
         - 'blue'           => ANSIColors.BLUE.value => ANSIColor(0, 0, 170, 255)
         - '12,34,56,128'   => Color(12, 34, 56, 128)
         - '(12, 34, 56)    => Color(12, 34, 56, 255)
        """
        string = string.strip().upper()

        if string in ANSI_COLOR_DICT:
            return ANSI_COLOR_DICT[string]

        if match := re.search(r"^#?([0-9A-F]{3,})$", string):
            css_color = match.group(1)
            arr: RGBA = np.array([0xFF] * 4, dtype=np.uint8)

            if len(css_color) >= 8:
                arr[:] = [int(css_color[i : i + 2], base=16) for i in range(0, 7, 2)]
            elif len(css_color) >= 6:
                arr[:3] = [int(css_color[i : i + 2], base=16) for i in range(0, 5, 2)]
            elif len(css_color) >= 4:
                arr[:] = [int(v * 2, base=16) for v in css_color[:4]]
            else:
                arr[:3] = [int(v * 2, base=16) for v in css_color[:3]]

            return Color(arr)

        if len(parts := re.split(r" *, *", string.strip(" ()"))[:4]) >= 3:
            arr: RGBA = np.array([0xFF] * 4, dtype=np.uint8)
            try:
                arr[: len(parts)] = [int(p) for p in parts]
                return Color(arr)
            except (ValueError, OverflowError):
                return None

        return None


class AnsiColor(Color):
    @property
    def ansi_codes(self):
        return [str(self.code)]

    @property
    def ansi_codes_background(self):
        return [str(self.bg_code)]

    @timer
    def __init__(self, name: str, red: int, green: int, blue: int, code: int, bg_code: int, alpha: int = 0xFF):
        self.array = np.array([red, green, blue, alpha], dtype=np.uint8)
        self.code = code
        self.bg_code = bg_code
        self.name = name

    def __str__(self):
        return self.name


# https://stackoverflow.com/questions/4842424/list-of-ansi-color-escape-sequences
ANSI_COLORS = [
    AnsiColor("BLACK", 0x00, 0x00, 0x00, 30, 40),
    AnsiColor("RED", 0xAA, 0x00, 0x00, 31, 41),
    AnsiColor("GREEN", 0x00, 0xAA, 0x00, 32, 42),
    AnsiColor("YELLOW", 0xAA, 0x55, 0x00, 33, 43),
    AnsiColor("BLUE", 0x00, 0x00, 0xAA, 34, 44),
    AnsiColor("MAGENTA", 0xAA, 0x00, 0xAA, 35, 45),
    AnsiColor("CYAN", 0x00, 0xAA, 0xAA, 36, 46),
    AnsiColor("WHITE", 0xAA, 0xAA, 0xAA, 37, 47),
    AnsiColor("BRIGHTBLACK", 0x55, 0x55, 0x55, 90, 100),
    AnsiColor("BRIGHTRED", 0xFF, 0x55, 0x55, 91, 101),
    AnsiColor("BRIGHTGREEN", 0x55, 0xFF, 0x55, 92, 102),
    AnsiColor("BRIGHTYELLOW", 0xFF, 0xFF, 0x55, 93, 103),
    AnsiColor("BRIGHTBLUE", 0x55, 0x55, 0xFF, 94, 104),
    AnsiColor("BRIGHTPURPLE", 0xFF, 0x55, 0xFF, 95, 105),
    AnsiColor("BRIGHTCYAN", 0x55, 0xFF, 0xFF, 96, 106),
    AnsiColor("BRIGHTWHITE", 0xFF, 0xFF, 0xFF, 97, 107),
]

ANSI_COLOR_DICT = {color.name: color for color in ANSI_COLORS}


@timer
def get_perceived_brightness(
    red: np.ndarray[tuple[int]],
    green: np.ndarray[tuple[int]],
    blue: np.ndarray[tuple[int]],
) -> np.ndarray[tuple[int], np.dtype[np.float64]]:
    # Calculates perceived brightness per algorithm:
    # https://pillow.readthedocs.io/en/stable/reference/Image.html#PIL.Image.Image.convert
    return red * 0.299 + green * 0.587 + blue * 0.114


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
    rgbc = np.stack(
        [
            rgb.max(axis=axis),
            np.take_along_axis(rgb, np.expand_dims((rgb.argmax(axis=axis) + 1) % 3, axis=axis), axis=axis).squeeze(),
            np.take_along_axis(rgb, np.expand_dims((rgb.argmax(axis=axis) + 2) % 3, axis=axis), axis=axis).squeeze(),
            np.ptp(rgb, axis=axis),
        ],
        axis=axis,
    )

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
    return np.stack(
        [
            # Hue:
            (
                rgb.argmax(axis=axis) * 2
                + np.divide(
                    rgbc.take(1, axis=axis) - rgbc.take(2, axis=axis),
                    rgbc.take(3, axis=axis),
                    where=rgbc.take(3, axis=axis) > 0,
                    out=np.zeros((*rgb.shape[:-1],)),
                )
            )
            / 6
            % 1
            * 360,
            # Saturation:
            np.divide(
                rgbc.take(3, axis=axis),
                rgbc.take(0, axis=axis),
                where=rgbc.take(0, axis=axis) > 0,
                out=np.zeros((*rgb.shape[:-1],)),
            )
            * 100,
            # Value:
            rgbc.take(0, axis=axis) / 0xFF * 100,
        ],
        axis=axis,
    )
