import enum
import math

from image2ascii.timing import timer


class ColorInferenceMethod(enum.StrEnum):
    MEDIAN = enum.auto()
    MOST_COMMON = enum.auto()


class ObjectFit(enum.StrEnum):
    """
    Borrowed from object-fit in CSS.

    CONTAIN: The item is scaled to maintain its aspect ratio while fitting
    within the container. The entire item is made to fill the container, while
    preserving its aspect ratio, so the item will be "letterboxed" or
    "pillarboxed" if its aspect ratio does not match the aspect ratio of the
    container.

    COVER: The item is sized to maintain its aspect ratio while filling the
    entire container. If the item's aspect ratio does not match the aspect
    ratio of its container, then the item will be clipped to fit.

    NONE: The item is not resized.

    SCALE_DOWN: The item is sized as if NONE or CONTAIN were specified,
    whichever would result in a smaller concrete item size.
    """

    CONTAIN = enum.auto()
    COVER = enum.auto()
    NONE = enum.auto()
    SCALE_DOWN = enum.auto()


class RoundMethod(enum.StrEnum):
    FLOOR = enum.auto()
    CEIL = enum.auto()
    ROUND = enum.auto()

    @timer
    def round(self, value: float):
        match self:
            case self.FLOOR:
                return int(value)
            case self.CEIL:
                return math.ceil(value)
            case self.ROUND:
                return round(value)


class TransparencyMethod(enum.StrEnum):
    BRIGHTNESS = enum.auto()
    BG_DISTANCE = enum.auto()
