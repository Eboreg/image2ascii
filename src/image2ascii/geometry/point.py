import dataclasses
from abc import ABC
from typing import Generic

from image2ascii.enums import RoundMethod
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


@dataclasses.dataclass
class PointF(AbstractPoint[float]):
    x: float
    y: float

    def to_point(self, method: RoundMethod = RoundMethod.FLOOR) -> "Point":
        return Point(method.round(self.x), method.round(self.y))
