from collections import namedtuple
from typing import Iterable, List, SupportsFloat, Tuple

from matplotlib.path import Path

from image2ascii.utils import timer

CropBox = namedtuple("CropBox", ["left", "upper", "right", "lower"], defaults=[0, 0, 0, 0])


class BaseShape:
    def __init__(self, char: str, width: int, height: int):
        self.char, self.width, self.height = char, width, height
        # Number of points enclosed by the containing box:
        self.box_size = width * height

    def likeness(self, nonzero_coords: List[Tuple[int, int]]) -> float:
        raise NotImplementedError


class FilledShape(BaseShape):
    """
    A completely filled shape, which means the likeness with any given
    boolmatrix is just the fraction of its members that are True.
    """
    @timer
    def likeness(self, nonzero_coords: List[Tuple[int, int]]) -> float:
        # Let's just let division by 0 raise its exception
        return len(nonzero_coords) / self.box_size


class EmptyShape(BaseShape):
    """
    A completely empty shape, which means the likeness with any given
    boolmatrix is just the fraction of its members that are False.
    """
    @timer
    def likeness(self, nonzero_coords: List[Tuple[int, int]]) -> float:
        return (self.box_size - len(nonzero_coords)) / self.box_size


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
        super().__init__(char, width, height)
        self.points = [(float(p[0]), float(p[1])) for p in points]
        self.path = Path([(p[0] * width, p[1] * height) for p in self.points], readonly=True)
        box_points = [(x + 1, y + 1) for x in range(self.width) for y in range(self.height)]
        # Number of points enclosed by this shape:
        self.filled_size = len([v for v in self.path.contains_points(box_points) if v])
        # Number of points NOT enclosed by this shape:
        self.unfilled_size = self.box_size - self.filled_size

    @timer
    def likeness(self, nonzero_coords: List[Tuple[int, int]]) -> float:
        """
        Returns fraction of filled points conforming to the shape.
        :param nonzero_coords: List of (x, y) tuples for filled points
        :returns: Float from 0.0 to 1.0, where 1.0 is perfect likeness between
            image and shape
        """
        if nonzero_coords:
            # Produces a list of booleans, telling us whether each of these
            # filled points is contained by the shape:
            containment = self.path.contains_points(nonzero_coords)
            # Number of filled points that are/are not contained by the shape:
            filled_points_within = len([v for v in containment if v])
            filled_points_outside = len(nonzero_coords) - filled_points_within
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
