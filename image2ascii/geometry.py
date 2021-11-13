from collections import UserList, namedtuple
from typing import Generic, List, Optional, SupportsFloat, Tuple, TypeVar

from matplotlib.path import Path

_T = TypeVar("_T")

CropBox = namedtuple("CropBox", ["left", "upper", "right", "lower"], defaults=[0, 0, 0, 0])


class Matrix(UserList, Generic[_T]):
    data: List[List[_T]]

    def __init__(self, width: int, height: int, empty_value: _T, data: Optional[List[_T]] = None):
        data = data or []
        self.width, self.height, self.empty_value = width, height, empty_value
        length = width * height
        if len(data) > length:
            data = data[:length]
        elif len(data) < length:
            data = data + [empty_value] * (length - len(data))
        self.data = [data[(row * width):(row * width) + width] for row in range(height)]

    def __getitem__(self, idx):
        if isinstance(idx, slice):
            data = self.data.copy()
            data = data[idx]
            return self.__class__(self.width, len(data), self.empty_value, [value for row in data for value in row])
        return self.data[idx]

    @property
    def length(self) -> int:
        return self.width * self.height

    def crop(self, box: Optional[CropBox] = None) -> CropBox:
        """
        If box is not given, crops away rows/columns with only
        self.empty_value. Also returns the CropBox for convenience.
        """
        box = box or self.get_crop_box()
        self.data = self.data[box.upper:box.lower]
        if box.left or box.right:
            for idx, row in enumerate(self.data):
                self.data[idx] = row[box.left:box.right]
        self.width = box.right - box.left
        self.height = box.lower - box.upper
        return box

    def get_crop_box(self) -> CropBox:
        left, upper = 0, 0
        lower = self.height
        right = self.width

        if not lower or not right:
            return CropBox()

        for row in self:
            if all([value == self.empty_value for value in row]):
                upper += 1
            else:
                break

        for row in self[::-1]:
            if all([value == self.empty_value for value in row]):
                lower -= 1
            else:
                break

        for col_idx in range(len(self[0])):
            if all([row[col_idx] == self.empty_value for row in self]):
                left += 1
            else:
                break

        for col_idx in range(len(self[0]) - 1, -1, -1):
            if all([row[col_idx] == self.empty_value for row in self]):
                right -= 1
            else:
                break

        return CropBox(left, upper, right, lower)


class Shape:
    def __init__(
        self,
        char: str,
        *points: Tuple[SupportsFloat, SupportsFloat],
        width: Optional[int] = None,
        height: Optional[int] = None,
    ):
        """
        :param points: Series of (x, y) values, together forming a polygon
            within which we will check the image pixels for being filled. The
            x and y values are relative: (0.0, 0.0) = top/left corner,
            (1.0, 1.0) = bottom right corner. Pixels outside this polygon will
            be checked for NOT being filled.
        """
        self.char = char
        self.points = [(float(p[0]), float(p[1])) for p in points]
        if width is not None and height is not None:
            self.init(width, height)

    def init(self, width: int, height: int):
        self.width, self.height = width, height
        self.path = Path([(p[0] * width, p[1] * height) for p in self.points])
        return self

    def likeness(self, boolmatrix: Matrix[bool]) -> float:
        """
        Fraction of selected area being filled + fraction of the rest being
        unfilled
        :param boolmatrix: Matrix of booleans, each representing one pixel in
            an image of size (self.width, self.height).
        :returns: Float from 0.0 to 1.0, where 1.0 is perfect likeness between
            image and shape
        """
        assert hasattr(self, "width") and hasattr(self, "height"), "Must run init() before likeness()"
        assert self.width == boolmatrix.width, \
            f"Matrix width ({boolmatrix.width}) differs from self.width ({self.width})"
        assert self.height == boolmatrix.height, \
            f"Matrix height ({boolmatrix.height}) differs from self.height ({self.height})"
        matches = 0
        for y in range(self.height):
            for x in range(self.width):
                # If imagedata for current pixel==True, actual pixel is filled.
                # If the pixel is within path, it _should_ be filled.
                if self.path.contains_point((x, y)) == boolmatrix[y][x]:
                    matches += 1
        return matches / boolmatrix.length
