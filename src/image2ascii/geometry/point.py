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


class Point(AbstractPoint[int]):
    def __init__(self, x: int, y: int):
        self.x = x
        self.y = y


class PointF(AbstractPoint[float]):
    def __init__(self, x: float, y: float):
        self.x = x
        self.y = y

    def to_point(self, method: RoundMethod = RoundMethod.FLOOR) -> "Point":
        return Point(method.round(self.x), method.round(self.y))


OptionalPointF = tuple[float, float] | PointF | None
