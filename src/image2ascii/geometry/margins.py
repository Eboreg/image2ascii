import dataclasses
from typing import Self

from image2ascii.color import Vi
from image2ascii.timing import timer
from image2ascii.types import ImageArray


@dataclasses.dataclass
class Margins:
    left: int = 0
    top: int = 0
    right: int = 0
    bottom: int = 0

    def __add__(self, other: "Margins | int"):
        if isinstance(other, Margins):
            return Margins(
                left=self.left + other.left,
                top=self.top + other.top,
                right=self.right + other.right,
                bottom=self.bottom + other.bottom,
            )
        return Margins(
            left=self.left + other,
            top=self.top + other,
            right=self.right + other,
            bottom=self.bottom + other,
        )

    def __sub__(self, other: "Margins | int") -> "Margins":
        if isinstance(other, Margins):
            return Margins(
                left=self.left - other.left,
                top=self.top - other.top,
                right=self.right - other.right,
                bottom=self.bottom - other.bottom,
            )
        return Margins(
            left=self.left - other,
            top=self.top - other,
            right=self.right - other,
            bottom=self.bottom - other,
        )

    def to_margins_f(self):
        return MarginsF(self.left, self.top, self.right, self.bottom)

    @classmethod
    @timer
    def from_visible(cls, matrix: ImageArray) -> Self:
        """
        Iterates through pixel arrays from all the image edges "inwards", each
        time stopping when an array contains at least one visible pixel.
        Returns margins for cropping `matrix` to the smallest possible array
        containing all the visible parts of the image.
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

        return cls(left=-left, top=-upper, right=right-width, bottom=lower-height)


@dataclasses.dataclass
class MarginsF:
    left: float = 0
    top: float = 0
    right: float = 0
    bottom: float = 0

    def __add__(self, other: "MarginsF | float"):
        if isinstance(other, MarginsF):
            return MarginsF(
                left=self.left + other.left,
                top=self.top + other.top,
                right=self.right + other.right,
                bottom=self.bottom + other.bottom,
            )
        return MarginsF(
            left=self.left + other,
            top=self.top + other,
            right=self.right + other,
            bottom=self.bottom + other,
        )

    def __sub__(self, other: "MarginsF | float"):
        if isinstance(other, MarginsF):
            return MarginsF(
                left=self.left - other.left,
                top=self.top - other.top,
                right=self.right - other.right,
                bottom=self.bottom - other.bottom,
            )
        return MarginsF(
            left=self.left - other,
            top=self.top - other,
            right=self.right - other,
            bottom=self.bottom - other,
        )
