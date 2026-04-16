import dataclasses
import itertools
import math
from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, Generic, Self

from image2ascii.color import Vi
from image2ascii.enums import RoundMethod
from image2ascii.timing import timer
from image2ascii.types import ImageArray, NumberT


if TYPE_CHECKING:
    from image2ascii.geometry import AbstractSize


class AbstractSubRect(ABC, Generic[NumberT]):
    """Subsection of a rectangle, defined by four offsets."""
    left: NumberT
    upper: NumberT
    right: NumberT
    lower: NumberT

    @property
    @abstractmethod
    def size(self) -> "AbstractSize[NumberT]": ...

    @abstractmethod
    def __mul__(self, other: "float | int | AbstractSize") -> "SubRectF": ...

    def __repr__(self) -> str:
        return (
            f"{self.__class__.__name__}(left={self.left}, upper={self.upper}, right={self.right}, lower={self.lower})"
        )

    def __str__(self) -> str:
        return self.__repr__()


class SubRectF(AbstractSubRect[float]):
    def __init__(self, left: float, upper: float, right: float, lower: float):
        self.left = left
        self.upper = upper
        self.right = right
        self.lower = lower

    @property
    def size(self):
        from image2ascii.geometry import SizeF

        return SizeF(self.right - self.left, self.lower - self.upper)

    @property
    def tuple(self):
        return (float(self.left), float(self.upper), float(self.right), float(self.lower))

    @timer
    def __mul__(self, other: "float | int | AbstractSize") -> "SubRectF":
        from image2ascii.geometry import AbstractSize

        if isinstance(other, AbstractSize):
            return SubRectF(
                left=round(self.left * other.width, 8),
                upper=round(self.upper * other.height, 8),
                right=round(self.right * other.width, 8),
                lower=round(self.lower * other.height, 8),
            )

        return SubRectF(
            left=round(self.left * other, 8),
            upper=round(self.upper * other, 8),
            right=round(self.right * other, 8),
            lower=round(self.lower * other, 8),
        )

    @timer
    def to_subrect(self, method: RoundMethod = RoundMethod.FLOOR, round_for_ratio: bool = False) -> "SubRect":
        if round_for_ratio:
            values = [[math.floor(value), math.ceil(value)] for value in self.tuple]
            subrects = sorted(
                [SubRect(*args) for args in itertools.product(*values)],
                key=lambda s: abs(s.size.ratio - self.size.ratio),
            )
            return subrects[0]

        return SubRect(
            left=method.round(self.left),
            upper=method.round(self.upper),
            right=method.round(self.right),
            lower=method.round(self.lower),
        )


@dataclasses.dataclass
class SubRect(AbstractSubRect[int]):
    left: int
    upper: int
    right: int
    lower: int

    @property
    def size(self):
        from image2ascii.geometry import Size

        return Size(self.right - self.left, self.lower - self.upper)

    @property
    def tuple(self):
        return (self.left, self.upper, self.right, self.lower)

    def __mul__(self, other: "float | int | AbstractSize") -> "SubRectF":
        return self.to_subrect_f() * other

    def to_subrect_f(self):
        return SubRectF(self.left, self.upper, self.right, self.lower)

    @classmethod
    @timer
    def from_visible(cls, matrix: ImageArray) -> Self:
        """
        Iterates through pixel arrays from all the image edges "inwards", each
        time stopping when an array contains at least one visible pixel.
        Returns the smallest possible box containing all the visible parts of
        the image.
        """
        height, width, _ = matrix.shape
        left, upper, right, lower = 0, 0, width, height

        for left in range(width):
            if matrix[:, left, Vi].any():
                break

        for upper in range(height):
            if matrix[upper, :, Vi].any():
                break

        for right in range(width, left, -1):
            if matrix[:, right - 1, Vi].any():
                break

        for lower in range(height, upper, -1):
            if matrix[lower - 1, :, Vi].any():
                break

        return cls(left, upper, right, lower)


class AbstractSubRect2(ABC, Generic[NumberT]):
    """Subsection of a rectangle, defined by four offsets."""
    outer: "AbstractSize[NumberT]"
    left: NumberT
    upper: NumberT
    right: NumberT
    lower: NumberT

    @property
    @abstractmethod
    def size(self) -> "AbstractSize[NumberT]": ...

    @abstractmethod
    def __mul__(self, other: "float | int | AbstractSize") -> "AbstractSubRect2": ...

    def __repr__(self) -> str:
        return (
            f"{self.__class__.__name__}(outer={self.outer}, left={self.left}, upper={self.upper}, right={self.right}, "
            f"lower={self.lower})"
        )

    def __str__(self) -> str:
        return self.__repr__()


@dataclasses.dataclass
class SubRectF2(AbstractSubRect2[float]):
    outer: "AbstractSize[float]"
    left: float
    upper: float
    right: float
    lower: float

    @property
    def size(self):
        from image2ascii.geometry import SizeF

        return SizeF(self.right - self.left, self.lower - self.upper)

    @property
    def tuple(self):
        return (float(self.left), float(self.upper), float(self.right), float(self.lower))

    @timer
    def __mul__(self, other: "float | int | AbstractSize") -> "SubRectF2":
        from image2ascii.geometry import AbstractSize

        if isinstance(other, AbstractSize):
            ratio = other / self.outer
            return SubRectF2(
                outer=other,
                left=round(self.left * ratio.width, 8),
                upper=round(self.upper * ratio.height, 8),
                right=round(self.right * ratio.width, 8),
                lower=round(self.lower * ratio.height, 8),
            )

        return SubRectF2(
            outer=self.outer * other,
            left=round(self.left * other, 8),
            upper=round(self.upper * other, 8),
            right=round(self.right * other, 8),
            lower=round(self.lower * other, 8),
        )

    @timer
    def to_subrect(self, method: RoundMethod = RoundMethod.FLOOR, round_for_ratio: bool = False) -> "SubRect":
        if round_for_ratio:
            values = [[math.floor(value), math.ceil(value)] for value in self.tuple]
            subrects = sorted(
                [SubRect(*args) for args in itertools.product(*values)],
                key=lambda s: abs(s.size.ratio - self.size.ratio),
            )
            return subrects[0]

        return SubRect(
            left=method.round(self.left),
            upper=method.round(self.upper),
            right=method.round(self.right),
            lower=method.round(self.lower),
        )


@dataclasses.dataclass
class SubRect2(AbstractSubRect2[int]):
    outer: "AbstractSize[int]"
    left: int
    upper: int
    right: int
    lower: int

    @property
    def size(self):
        from image2ascii.geometry import Size

        return Size(self.right - self.left, self.lower - self.upper)

    @property
    def tuple(self):
        return (self.left, self.upper, self.right, self.lower)

    @timer
    def __mul__(self, other: "float | int | AbstractSize") -> "AbstractSubRect2":
        if isinstance(other, int):
            return SubRect2(
                outer=self.outer * other,
                left=round(self.left * other, 8),
                upper=round(self.upper * other, 8),
                right=round(self.right * other, 8),
                lower=round(self.lower * other, 8),
            )

        return self.to_subrect_f() * other

    def to_subrect_f(self):
        return SubRectF2(self.outer, self.left, self.upper, self.right, self.lower)

    @classmethod
    @timer
    def from_visible(cls, matrix: ImageArray) -> Self:
        """
        Iterates through pixel arrays from all the image edges "inwards", each
        time stopping when an array contains at least one visible pixel.
        Returns the smallest possible box containing all the visible parts of
        the image.
        """
        from image2ascii.geometry import Size

        height, width, _ = matrix.shape
        left, upper, right, lower = 0, 0, width, height

        for left in range(width):
            if matrix[:, left, Vi].any():
                break

        for upper in range(height):
            if matrix[upper, :, Vi].any():
                break

        for right in range(width, left, -1):
            if matrix[:, right - 1, Vi].any():
                break

        for lower in range(height, upper, -1):
            if matrix[lower - 1, :, Vi].any():
                break

        return cls(Size(width, height), left, upper, right, lower)
