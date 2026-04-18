import dataclasses
from abc import ABC
from typing import TYPE_CHECKING, Generic, Self

from image2ascii.enums import RoundMethod
from image2ascii.timing import timer
from image2ascii.types import NumberT


if TYPE_CHECKING:
    from image2ascii.geometry import Point, PointF, Size, SizeF


class AbstractRect(ABC, Generic[NumberT]):
    x: NumberT
    y: NumberT
    width: NumberT
    height: NumberT

    @property
    def bottom(self) -> NumberT:
        return self.y + self.height

    @property
    def crop_tuple(self) -> tuple[NumberT, NumberT, NumberT, NumberT]:
        return (self.x, self.y, self.right, self.bottom)

    @property
    def left(self) -> NumberT:
        return self.x

    @property
    def right(self) -> NumberT:
        return self.x + self.width

    @property
    def top(self) -> NumberT:
        return self.y


@dataclasses.dataclass
class Rect(AbstractRect[int]):
    x: int
    y: int
    width: int
    height: int

    @property
    def size(self) -> "Size":
        from image2ascii.geometry import Size

        return Size(self.width, self.height)

    def to_rect_f(self) -> "RectF":
        return RectF(self.x, self.y, self.width, self.height)

    @classmethod
    def from_points(cls, top_left: "Point", bottom_right: "Point") -> Self:
        return cls(x=top_left.x, y=top_left.y, width=bottom_right.x - top_left.x, height=bottom_right.y - top_left.y)


@dataclasses.dataclass
class RectF(AbstractRect[float]):
    x: float
    y: float
    width: float
    height: float

    @property
    def size(self) -> "SizeF":
        from image2ascii.geometry import SizeF

        return SizeF(self.width, self.height)

    def move_by(self, x: float, y: float) -> "RectF":
        return RectF(x=self.x + x, y=self.y + y, width=self.width, height=self.height)

    @timer
    def to_rect(self, method: RoundMethod = RoundMethod.FLOOR, round_for_ratio: bool = False) -> "Rect":
        size = self.size.to_size(method=method, round_for_ratio=round_for_ratio)

        return Rect(
            x=method.round(self.x),
            y=method.round(self.y),
            width=size.width,
            height=size.height,
        )

    @classmethod
    def from_points(cls, top_left: "PointF", bottom_right: "PointF") -> Self:
        return cls(x=top_left.x, y=top_left.y, width=bottom_right.x - top_left.x, height=bottom_right.y - top_left.y)
