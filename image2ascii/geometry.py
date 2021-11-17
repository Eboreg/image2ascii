from collections import UserList, namedtuple
from typing import Generic, Iterable, List, Optional, SupportsFloat, Tuple, TypeVar

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
    def size(self) -> int:
        return self.width * self.height

    @property
    def non_empty_points(self) -> List[Tuple[int, int]]:
        """
        Returns list of coordinates for those values in the matrix that are
        not self.empty_value.
        """
        return [
            (x + 1, y + 1)
            for y, row in enumerate(self.data)
            for x, value in enumerate(row)
            if value != self.empty_value
        ]

    def copy(self):
        return self.__class__(
            width=self.width,
            height=self.height,
            empty_value=self.empty_value,
            data=[dd for d in self.data for dd in d]
        )

    def crop(self, box: CropBox):
        """
        If box is not given, crops away rows/columns with only
        self.empty_value. Returns cropped copy of itself.
        Not used ATM.
        """
        matrix = self.copy()
        matrix.data = matrix.data[box.upper:box.lower]
        if box.left or box.right:
            for idx, row in enumerate(matrix.data):
                matrix.data[idx] = row[box.left:box.right]
        matrix.width = box.right - box.left
        matrix.height = box.lower - box.upper
        return matrix

    def flatten(self) -> List[_T]:
        return [x for y in self.data for x in y]

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


class BaseShape:
    def __init__(self, char: str):
        self.char = char

    def likeness(self, boolmatrix: Matrix[bool]) -> float:
        raise NotImplementedError


class FilledShape(BaseShape):
    """
    A completely filled shape, which means the likeness with any given
    boolmatrix is just the fraction of its members that are True.
    """
    def likeness(self, boolmatrix: Matrix[bool]) -> float:
        # Let's just let division by 0 raise its exception
        return len([v for v in boolmatrix.flatten() if v]) / boolmatrix.size


class EmptyShape(BaseShape):
    """
    A completely empty shape, which means the likeness with any given
    boolmatrix is just the fraction of its members that are False.
    """
    def likeness(self, boolmatrix: Matrix[bool]) -> float:
        return len([v for v in boolmatrix.flatten() if not v]) / boolmatrix.size


class PolygonShape(BaseShape):
    def __init__(
        self,
        char: str,
        width: int,
        height: int,
        points: Iterable[Tuple[SupportsFloat, SupportsFloat]],
    ):
        """
        :param points: Series of (x, y) values, together forming a polygon
            within which we will check the image pixels for being filled. The
            x and y values are relative: (0.0, 0.0) = top/left corner,
            (1.0, 1.0) = bottom right corner. Pixels outside this polygon will
            be checked for NOT being filled.
        """
        super().__init__(char)
        self.width, self.height = width, height
        self.points = [(float(p[0]), float(p[1])) for p in points]
        self.path = Path([(p[0] * width, p[1] * height) for p in self.points], readonly=True)
        box_points = [(x + 1, y + 1) for x in range(self.width) for y in range(self.height)]
        # Number of points enclosed by the containing box:
        self.box_size = width * height
        # Number of points enclosed by this shape:
        self.filled_size = len([v for v in self.path.contains_points(box_points) if v])
        # Number of points NOT enclosed by this shape:
        self.unfilled_size = self.box_size - self.filled_size

    def likeness(self, boolmatrix: Matrix[bool]) -> float:
        """
        Fraction of selected area being filled + fraction of the rest being
        unfilled
        :param boolmatrix: Matrix of booleans, each representing one pixel in
            an image of size (self.width, self.height).
        :returns: Float from 0.0 to 1.0, where 1.0 is perfect likeness between
            image and shape
        """
        assert self.width == boolmatrix.width, \
            f"Matrix width ({boolmatrix.width}) differs from self.width ({self.width})"
        assert self.height == boolmatrix.height, \
            f"Matrix height ({boolmatrix.height}) differs from self.height ({self.height})"

        # Coordinates for each filled point in the matrix:
        points = boolmatrix.non_empty_points

        if points:
            # Produces a list of booleans, telling us whether each of these
            # filled points is contained by the shape:
            containment = self.path.contains_points(points)
            # Number of filled points that are/are not contained by the shape:
            filled_points_within = len([v for v in containment if v])
            filled_points_outside = len(points) - filled_points_within
        else:
            # contains_points() can't handle an empty list
            filled_points_within = filled_points_outside = 0

        # Number of UNfilled points NOT contained by the shape:
        unfilled_points_outside = self.unfilled_size - filled_points_outside

        # What we want is to have as many points as possible that conform
        # to the shape, i.e. are filled when they are inside the shape, and
        # unfilled when they are outside it:
        conforming_points = filled_points_within + unfilled_points_outside

        # In other words, we want this quota as high as possible:
        return conforming_points / self.box_size

        matches = 0
        for y in range(self.height):
            for x in range(self.width):
                # If imagedata for current pixel==True, actual pixel is filled.
                # If the pixel is within path, it _should_ be filled.
                if self.path.contains_point((x, y), radius=1) == boolmatrix[y][x]:
                    matches += 1
        return matches / boolmatrix.length
