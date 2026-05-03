import dataclasses
from abc import ABC
from typing import Generic

from image2ascii.types import NumberT


class AbstractPoint(ABC, Generic[NumberT]):
    x: NumberT
    y: NumberT

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}(x={self.x}, y={self.y})"

    def __str__(self) -> str:
        return self.__repr__()


@dataclasses.dataclass
class Point(AbstractPoint[int]):
    x: int
    y: int

    def to_point_f(self) -> "PointF":
        return PointF(self.x, self.y)


@dataclasses.dataclass
class PointF(AbstractPoint[float]):
    x: float
    y: float

    def __add__(self, other: "float | PointF") -> "PointF":
        if isinstance(other, PointF):
            return PointF(self.x + other.x, self.y + other.y)
        return PointF(self.x + other, self.y + other)

    def __mul__(self, other: "float | PointF") -> "PointF":
        if isinstance(other, PointF):
            return PointF(self.x * other.x, self.y * other.y)
        return PointF(self.x * other, self.y * other)

    def coerce_between(self, start: "PointF", end: "PointF"):
        return PointF(min(max(self.x, start.x), end.x), min(max(self.y, start.y), end.y))
