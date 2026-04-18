import dataclasses
import itertools
import math
from abc import ABC
from collections.abc import Iterator
from typing import TYPE_CHECKING, Generic

from image2ascii.enums import RoundMethod
from image2ascii.timing import timer
from image2ascii.types import NumberT
from image2ascii.utils import partition


if TYPE_CHECKING:
    from image2ascii.geometry import PointF, RectF, SubRectF


class AbstractSize(ABC, Generic[NumberT]):
    width: NumberT
    height: NumberT

    @property
    def ratio(self) -> float:
        return self.width / self.height

    @property
    def tuple(self) -> tuple[NumberT, NumberT]:
        return (self.width, self.height)

    def __eq__(self, value: object) -> bool:
        if isinstance(value, AbstractSize):
            return value.width == self.width and value.height == self.height
        return False

    def __lt__(self, other: "AbstractSize") -> bool:
        return self.width < other.width or self.height < other.height

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}(width={self.width}, height={self.height})"

    def __str__(self) -> str:
        return self.__repr__()

    def __truediv__(self, other: "AbstractSize") -> "SizeF":
        return SizeF(self.width / other.width, self.height / other.height)


class SizeF(AbstractSize[float]):
    def __init__(self, width: float, height: float):
        self.width = width
        self.height = height

    @timer
    def __add__(self, other: "SizeF") -> "SizeF":
        return SizeF(self.width + other.width, self.height + other.height)

    @timer
    def __mul__(self, other: "SizeF | float") -> "SizeF":
        if isinstance(other, SizeF):
            return SizeF(self.width * other.width, self.height * other.height)
        return SizeF(self.width * other, self.height * other)

    def crop(self, container: "SizeF", center: "PointF | None" = None) -> "SubRectF":
        from image2ascii.geometry import PointF, RectF, SubRectF

        center = center or PointF(0.5, 0.5)
        left = max(self.width - container.width, 0) * center.x
        top = max(self.height - container.height, 0) * center.y
        right = left + min(container.width, self.width)
        bottom = top + min(container.height, self.height)

        return SubRectF(self, RectF(x=left, y=top, width=right - left, height=bottom - top))

    @timer
    def fit_inside(self, other: "SizeF", grow: bool = True) -> "SizeF":
        if not grow and self.width <= other.width and self.height <= other.height:
            return self
        if self.ratio < other.ratio:
            return SizeF(other.height * self.ratio, other.height)
        return SizeF(other.width, other.width / self.ratio)

    @timer
    def fit_outside(self, other: "AbstractSize") -> "SizeF":
        if self.ratio > other.ratio:
            return SizeF(other.height * self.ratio, other.height)
        return SizeF(other.width, other.width / self.ratio)

    @timer
    def fit_ratio(self, ratio: float) -> "SizeF":
        if ratio < self.ratio:
            return SizeF(self.height * ratio, self.height)
        return SizeF(self.width, self.width / ratio)

    def to_rect_f(self, x: float = 0, y: float = 0) -> "RectF":
        from image2ascii.geometry import RectF

        return RectF(x, y, self.width, self.height)

    @timer
    def to_size(self, method: RoundMethod = RoundMethod.FLOOR, round_for_ratio: bool = False) -> "Size":
        if round_for_ratio:
            values = [[math.floor(value), math.ceil(value)] for value in self.tuple]
            sizes = sorted(
                [Size(*args) for args in itertools.product(*values)],
                key=lambda s: abs(s.ratio - self.ratio),
            )
            return sizes[0]

        return Size(method.round(self.width), method.round(self.height))


class Size(AbstractSize[int]):
    def __init__(self, width: int, height: int):
        self.width = width
        self.height = height

    @timer
    def __add__(self, other: "Size") -> "Size":
        return Size(self.width + other.width, self.height + other.height)

    @timer
    def __mul__(self, other: "Size | int") -> "Size":
        if isinstance(other, Size):
            return Size(self.width * other.width, self.height * other.height)
        return Size(self.width * other, self.height * other)

    @timer
    def partition(self, columns: int, rows: int) -> Iterator["IndexedSizePartition"]:
        """
        When partitioning into more parts than we have width/height (i.e. the
        desired output has more characters than the source image has pixels),
        some `partition()` results will be 0. Since we still want to fill those
        pixels with something, we borrow from the future (i.e. the next
        column/row) by returning a rectangle of size (1, 1) anyway.

         - But what if we're already on the last column/row?
         - In that case, the partitioning result is guaranteed to be > 0,
        thanks to how `partition()` works.
        """
        assert self.width >= columns
        assert self.height >= rows

        column_widths = partition(self.width, columns)
        row_heights = partition(self.height, rows)
        top = 0

        for row, height in enumerate(row_heights):
            left = 0

            for column, width in enumerate(column_widths):
                yield IndexedSizePartition(
                    top=top,
                    bottom=top + max(height, 1),
                    left=left,
                    right=left + max(width, 1),
                    column=column,
                    row=row,
                )
                left += width

            top += height

    def to_size_f(self) -> "SizeF":
        return SizeF(self.width, self.height)


@dataclasses.dataclass
class IndexedSizePartition:
    """
    A sized and positioned rectangle that occupies a specific, indexed position
    in a container.
    """
    top: int
    bottom: int
    left: int
    right: int
    column: int
    row: int
