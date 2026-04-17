from abc import ABC
from typing import TYPE_CHECKING, Generic

from image2ascii.timing import timer
from image2ascii.types import NumberT


if TYPE_CHECKING:
    from image2ascii.geometry import AbstractSize, PointF, SubRectF


class AbstractPositionedBox(ABC, Generic[NumberT]):
    """
    top, left: the positioned object's top & left position, relative to the
    viewport. If e.g. top is negative, it means the object's top is positioned
    that length _above_ the viewport and the object is therefore cut off at the
    top.
    """

    size: "AbstractSize[NumberT]"
    viewport: "AbstractSize[NumberT]"
    top: NumberT
    left: NumberT
    bottom: NumberT
    right: NumberT

    def __repr__(self) -> str:
        return (
            f"{self.__class__.__name__}(size={self.size}, viewport={self.viewport}, top={self.top}, left={self.left})"
        )

    def __str__(self) -> str:
        return self.__repr__()


class PositionedBoxF(AbstractPositionedBox[float]):
    @timer
    def __init__(
        self,
        size: "AbstractSize[float]",
        viewport: "AbstractSize[float]",
        top: float = 0.0,
        left: float = 0.0,
    ):
        self.size = size
        self.viewport = viewport
        self.top = top
        self.left = left
        self.bottom = self.top + self.size.height
        self.right = self.left + self.size.width

    @property
    def visible_box(self) -> "SubRectF":
        from image2ascii.geometry import SubRectF

        left = max(-self.left, 0)
        upper = max(-self.top, 0)
        right = min(self.size.width + self.left, self.viewport.width) - self.left
        lower = min(self.size.height + self.top, self.viewport.height) - self.top
        return SubRectF(left, upper, right, lower)

    @timer
    def place_relatively(self, point: "PointF | tuple[float, float]") -> "PositionedBoxF":
        from image2ascii.geometry import PointF

        hidden_height = self.size.height - self.viewport.height
        hidden_width = self.size.width - self.viewport.width
        x = point.x if isinstance(point, PointF) else point[0]
        y = point.y if isinstance(point, PointF) else point[1]

        return PositionedBoxF(
            size=self.size,
            viewport=self.viewport,
            top=round(hidden_height * -y, 8),
            left=round(hidden_width * -x, 8),
        )

    @timer
    def scale(self, size: "AbstractSize"):
        ratio = size / self.size
        return PositionedBoxF(
            size=size,
            viewport=self.viewport * ratio,
            top=self.top * ratio.height,
            left=self.left * ratio.width,
        )

    @timer
    def zoom(self, factor: float) -> "PositionedBoxF":
        """
        Resizes box uniformly by the given factor. Will not change box
        position.
        """
        return PositionedBoxF(self.size * factor, self.viewport, self.top, self.left)


class PositionedBox(AbstractPositionedBox[int]):
    @timer
    def __init__(self, size: "AbstractSize[int]", viewport: "AbstractSize[int]", top: int = 0, left: int = 0):
        self.size = size
        self.viewport = viewport
        self.top = top
        self.left = left
        self.bottom = self.top + self.size.height
        self.right = self.left + self.size.width


class PositionedBoxPartition(PositionedBox):
    @timer
    def __init__(
        self,
        size: "AbstractSize[int]",
        viewport: "AbstractSize[int]",
        column: int,
        row: int,
        top: int = 0,
        left: int = 0,
    ):
        super().__init__(size, viewport, top, left)
        self.column = column
        self.row = row

    def __repr__(self) -> str:
        return (
            f"{self.__class__.__name__}(size={self.size}, viewport={self.viewport}, top={self.top}, left={self.left}, "
            f"column={self.column}, row={self.row})"
        )
