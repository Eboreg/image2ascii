import dataclasses
from typing import TYPE_CHECKING, Self

from image2ascii.color import Vi
from image2ascii.enums import RoundMethod
from image2ascii.timing import timer
from image2ascii.types import ImageArray


if TYPE_CHECKING:
    from image2ascii.geometry import PointF, Rect, RectF, Size, SizeF


@dataclasses.dataclass
class SubRect:
    """A sized and positioned rectangle in relation to a sized rectangle."""
    container: "Size"
    rect: "Rect"

    @property
    def bottom(self) -> int:
        return self.rect.bottom

    @property
    def crop_tuple(self) -> tuple[int, int, int, int]:
        return self.rect.crop_tuple

    @property
    def left(self) -> int:
        return self.rect.left

    @property
    def right(self) -> int:
        return self.rect.right

    @property
    def top(self) -> int:
        return self.rect.top

    def __bool__(self) -> bool:
        return self.container != self.rect.size

    def to_subrect_f(self) -> "SubRectF":
        return SubRectF(container=self.container.to_size_f(), rect=self.rect.to_rect_f())

    @classmethod
    @timer
    def from_visible(cls, matrix: ImageArray) -> Self:
        """
        Iterates through pixel arrays from all the image edges "inwards", each
        time stopping when an array contains at least one visible pixel.
        Returns the smallest possible box containing all the visible parts of
        the image.
        """
        from image2ascii.geometry import Rect, Size

        height, width, _ = matrix.shape
        left, top, right, bottom = 0, 0, width, height

        for left in range(width):
            if matrix[:, left, Vi].any():
                break

        for top in range(height):
            if matrix[top, :, Vi].any():
                break

        for right in range(width, left, -1):
            if matrix[:, right - 1, Vi].any():
                break

        for bottom in range(height, top, -1):
            if matrix[bottom - 1, :, Vi].any():
                break

        return cls(Size(width, height), Rect(left, top, right - left, bottom - top))


@dataclasses.dataclass
class SubRectF:
    """A sized and positioned rectangle in relation to a sized rectangle."""
    container: "SizeF"
    rect: "RectF"

    def crop_to_size(self, size: "SizeF", center: "PointF | None" = None) -> "SubRectF":
        """Center is relative to the current rect size, not to container."""
        new_subrect = self.rect.size.crop(size, center)
        return SubRectF(container=self.container, rect=new_subrect.rect.move_by(self.rect.x, self.rect.y))

    def scale_container(self, container: "SizeF") -> "SubRectF":
        from image2ascii.geometry import RectF

        ratio = container / self.container
        rect = RectF(
            x=self.rect.x * ratio.width,
            y=self.rect.y * ratio.height,
            width=self.rect.width * ratio.width,
            height=self.rect.height * ratio.height,
        )
        return SubRectF(container=container, rect=rect)

    @timer
    def to_subrect(self, method: RoundMethod = RoundMethod.FLOOR, round_for_ratio: bool = False) -> "SubRect":
        return SubRect(
            container=self.container.to_size(method=method, round_for_ratio=round_for_ratio),
            rect=self.rect.to_rect(method=method, round_for_ratio=round_for_ratio),
        )
