from abc import ABC, abstractmethod
from typing import ClassVar, Literal

import numpy as np

from image2ascii.color import ANSI_COLORS, A, Color, Vi
from image2ascii.enums import ColorInferenceMethod
from image2ascii.timing import timer
from image2ascii.types import ImageArray


class AbstractColorConverter(ABC):
    SHORTHAND: ClassVar[str]

    @abstractmethod
    def closest(self, color: Color) -> Color | None:
        # The best match out of the colours this converter is allowed to use.
        ...

    @timer
    def get_section_color(self, section: ImageArray, inference_method: ColorInferenceMethod) -> Color | None:
        color: Color | None = None

        # Shortcut if there is only one colour (= a 1-pixel section):
        if section.shape[1] == 1:
            # If that pixel is visible, use it:
            if section[0, 0, Vi]:
                color = Color(section[0, 0, : A + 1])

        else:
            # Generate a 2-d RGBA data array for points where visibility > 0:
            colors = section[section[:, :, Vi] > 0, : A + 1]

            if colors.shape[0] == 1:
                color = Color(colors[0])

            elif colors.size and inference_method == ColorInferenceMethod.MOST_COMMON:
                view = colors.view(np.dtype((np.void, colors.dtype.itemsize * colors.shape[1])))
                uniq, counts = np.unique(view, return_counts=True)
                color = Color(colors[np.flatnonzero(view == uniq[counts.argmax()])[0]])

            elif colors.size and inference_method == ColorInferenceMethod.MEDIAN:
                k = colors.shape[0] // 2
                color = Color(np.partition(colors, k, axis=0)[k])

        return self.closest(color) if color else None


class NullColorConverter(AbstractColorConverter):
    """No colours at all. :-("""
    SHORTHAND = "null"

    def closest(self, color):
        return None

    def get_section_color(self, section, inference_method):
        return None


class GrayScaleColorConverter(AbstractColorConverter):
    SHORTHAND = "grayscale"

    @timer
    def closest(self, color: Color):
        return color.to_grayscale()


class AnsiColorConverter(AbstractColorConverter):
    SHORTHAND = "ansi"

    color_matrix: np.ndarray[tuple[Literal[16], Literal[3]], np.dtype[np.int64]]

    @timer
    def __init__(self):
        # Needs to be int64 because of the arithmetics done in self.closest():
        self.color_matrix = np.array([c.array for c in ANSI_COLORS], dtype=np.int64)

    @timer
    def closest(self, color):
        distances = color.get_distances(self.color_matrix)
        return ANSI_COLORS[np.argmin(distances)]


class FullRGBColorConverter(AbstractColorConverter):
    SHORTHAND = "rgb"

    def closest(self, color):
        return color
