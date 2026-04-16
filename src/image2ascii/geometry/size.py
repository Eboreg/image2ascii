import itertools
import math
from abc import ABC, abstractmethod
from collections.abc import Iterator
from typing import TYPE_CHECKING, Generic, overload

from PIL import Image

from image2ascii.enums import ObjectFit, RoundMethod
from image2ascii.timing import timer
from image2ascii.types import NumberT
from image2ascii.utils import partition


if TYPE_CHECKING:
    from image2ascii.geometry import PointF, PositionedBoxPartition, SubRectF


class AbstractSize(ABC, Generic[NumberT]):
    width: NumberT
    height: NumberT

    @property
    @abstractmethod
    def ratio(self) -> float: ...

    @property
    def tuple(self) -> tuple[NumberT, NumberT]:
        return (self.width, self.height)

    @overload
    def __add__(self: "Size", other: "Size") -> "Size": ...

    @overload
    def __add__(self: "AbstractSize", other: "SizeF") -> "SizeF": ...

    @overload
    def __add__(self: "SizeF", other: "AbstractSize") -> "SizeF": ...

    @timer
    def __add__(self, other: "AbstractSize"):
        if isinstance(self, Size) and isinstance(other, Size):
            return Size(self.width + other.width, self.height + other.height)
        return SizeF(self.width + other.width, self.height + other.height)

    def __floordiv__(self, other: "AbstractSize") -> "Size":
        return Size(int(self.width / other.width), int(self.height / other.height))

    def __lt__(self, other: "AbstractSize") -> bool:
        return self.width < other.width or self.height < other.height

    @overload
    def __mul__(self: "AbstractSize[int]", other: "Size | int") -> "Size": ...

    @overload
    def __mul__(self, other: "SizeF | float") -> "SizeF": ...

    @abstractmethod
    def __mul__(self, other: "AbstractSize | float") -> "AbstractSize": ...

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}(width={self.width}, height={self.height})"

    def __str__(self) -> str:
        return self.__repr__()

    @timer
    def __sub__(self, other: "AbstractSize") -> "SubRectF":
        from image2ascii.geometry import SubRectF

        height_diff = self.height - other.height
        width_diff = self.width - other.width

        return SubRectF(
            left=round(width_diff / 2, 8),
            upper=round(height_diff / 2, 8),
            right=round(self.width - (width_diff / 2), 8),
            lower=round(self.height - (height_diff / 2), 8),
        )

    def __truediv__(self, other: "AbstractSize") -> "SizeF":
        return SizeF(self.width / other.width, self.height / other.height)

    @timer
    def fit_inside(self, other: "AbstractSize", grow: bool = True) -> "SizeF":
        if not grow and self.width <= other.width and self.height <= other.height:
            return self.to_size_f()
        if self.ratio < other.ratio:
            return SizeF(round(other.height * self.ratio, 8), other.height)
        return SizeF(other.width, round(other.width / self.ratio, 8))

    @timer
    def fit_ratio(self, ratio: float) -> "SizeF":
        if ratio < self.ratio:
            return SizeF(self.height * ratio, self.height)
        return SizeF(self.width, self.width / ratio)

    @abstractmethod
    def to_size(self, method: RoundMethod = RoundMethod.FLOOR) -> "Size": ...

    @abstractmethod
    def to_size_f(self) -> "SizeF": ...


class SizeF(AbstractSize[float]):
    def __init__(self, width: float, height: float):
        self.width = width
        self.height = height

    @property
    def ratio(self) -> float:
        return self.width / self.height

    def __eq__(self, value: object) -> bool:
        if isinstance(value, AbstractSize):
            return value.width == self.width and value.height == self.height
        return False

    @timer
    def __mul__(self, other: "AbstractSize | float") -> "SizeF":
        if isinstance(other, AbstractSize):
            other_width, other_height = other.width, other.height
        else:
            other_width, other_height = other, other
        return SizeF(round(self.width * other_width, 8), round(self.height * other_height, 8))

    @timer
    def place_inside(self, container: "SizeF", object_fit: ObjectFit) -> "PlacedSizeF":
        """Not used ATM, buy maybe some day?"""

        def contain():
            if self.ratio < container.ratio:
                return container.height * self.ratio, container.height
            return container.width, container.width / self.ratio

        match object_fit:
            case ObjectFit.CONTAIN:
                width, height = contain()
            case ObjectFit.COVER:
                if self.ratio < container.ratio:
                    width, height = container.width, container.width / self.ratio
                else:
                    width, height = container.height * self.ratio, container.height
            case ObjectFit.NONE:
                width, height = self.width, self.height
            case ObjectFit.SCALE_DOWN:
                if self.width <= container.width and self.height <= container.height:
                    width, height = self.width, self.height
                else:
                    width, height = contain()

        return PlacedSizeF(width=width, height=height, container=container)

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

    def to_size_f(self) -> "SizeF":
        return self


class Size(AbstractSize[int]):
    def __init__(self, width: int, height: int):
        self.width = width
        self.height = height

    @property
    def ratio(self) -> float:
        return self.width / self.height

    def __eq__(self, value: object) -> bool:
        if isinstance(value, AbstractSize):
            return self.width == value.width and self.height == value.height
        return False

    @overload
    def __mul__(self, other: "Size | int") -> "Size": ...

    @overload
    def __mul__(self, other: "SizeF | float") -> "SizeF": ...

    @timer
    def __mul__(self, other: "AbstractSize | float"):
        if isinstance(other, Size):
            return Size(self.width * other.width, self.height * other.height)
        if isinstance(other, int):
            return Size(self.width * other, self.height * other)
        return self.to_size_f() * other

    @timer
    def partition(self, columns: int, rows: int) -> Iterator["PositionedBoxPartition"]:
        """
        EDIT: The safeguard described below is not super relevant anymore,
        since AsciiImage.prepare() should make sure images are always at least
        as large as the number of characters they will be turned into.

        When partitioning into more parts than we have width/height (i.e. the
        desired output has more characters than the source image has pixels),
        some `partition()` results will be 0. Since we still want to fill those
        pixels with something, we borrow from the future (i.e. the next
        column/row) by returning a Size(1, 1) anyway.

         - But what if we're already on the last column/row?
         - In that case, the partitioning result is guaranteed to be > 0,
        thanks to how `partition()` works.
        """
        from image2ascii.geometry import PositionedBoxPartition

        assert self.width >= columns
        assert self.height >= rows

        column_widths = partition(self.width, columns)
        row_heights = partition(self.height, rows)
        top = 0

        for row, height in enumerate(row_heights):
            left = 0

            for column, width in enumerate(column_widths):
                yield PositionedBoxPartition(
                    size=Size(max(width, 1), max(height, 1)),
                    viewport=self,
                    column=column,
                    row=row,
                    top=top,
                    left=left,
                )
                left += width

            top += height

    def to_size(self, method: RoundMethod = RoundMethod.FLOOR) -> "Size":
        return self

    def to_size_f(self) -> "SizeF":
        return SizeF(self.width, self.height)

    @classmethod
    def i(cls, image: Image.Image):
        return cls(image.width, image.height)


class PlacedSizeF(SizeF):
    """
    SizeF that is placed inside a containing SizeF, at a specific position.

    It is possible for the item to be larger than the container, in which case
    there will be overflow.

    self.position is relative to the topleft edge _of the container_; i.e.
    self.position.x == 10 means a 10 pt left margin, whereas self.position.x ==
    -10 means the 10 leftmost pt are invisible.

    If constructed with position=None, the item will be centered.

    Not used ATM, buy maybe some day?
    """

    @timer
    def __init__(self, width: float, height: float, container: "SizeF", position: "PointF | None" = None):
        from image2ascii.geometry import PointF

        super().__init__(width, height)

        if position is None:
            position = PointF(x=(container.width - width) / 2, y=(container.height - height) / 2)

        self.position = position
        self.container = container

    def __repr__(self) -> str:
        return (
            f"{self.__class__.__name__}(width={self.width}, height={self.height}, container={self.container}, "
            f"position={self.position})"
        )
