from abc import ABC, abstractmethod
from typing import ClassVar, Literal

import numpy as np
from matplotlib.path import Path
from matplotlib.transforms import Affine2D

from image2ascii.color import Vi
from image2ascii.timing import timer
from image2ascii.types import ImageArray


class Shape:
    """
    shades
    ------
    Alternative characters for semi-transparent sections. The 2nd tuple member
    is the _minimum_ opacity for which to use this character (scale 0 - 1).
    """
    char: str
    area: float
    shades: list[tuple[str, float]]

    def __init__(self, char: str, shades: list[tuple[str, float]] | None = None):
        self.char = char
        self.shades = shades or []
        self.shades.append((char, 1))
        self.shades = sorted(self.shades, key=lambda s: s[1])
        self.supports_opacity = len(self.shades) > 1

    def __repr__(self):
        return f"{self.__class__.__name__}(char='{self.char}')"

    def __str__(self):
        return self.__repr__()

    def char_for_opacity(self, opacity: float) -> str:
        return [s for s in self.shades if s[1] >= min(opacity, 1)][0][0]

    @abstractmethod
    def likeness(self, visible_points: np.ndarray[tuple[int, int], np.dtype[np.float64]], section_size: int) -> float:
        ...


class FilledShape(Shape):
    """
    A completely filled shape, which means the likeness with any given
    boolmatrix is just the fraction of its members that are True.
    """
    area = 1.0

    @timer
    def likeness(self, visible_points, section_size) -> float:
        return visible_points.shape[0] / section_size if section_size else 0


class EmptyShape(Shape):
    """
    A completely empty shape, which means the likeness with any given
    boolmatrix is just the fraction of its members that are False.
    """
    area = 0.0

    @timer
    def likeness(self, visible_points, section_size) -> float:
        return (section_size - visible_points.shape[0]) / section_size if section_size else 0


class BiColorShape(Shape):
    filled_part: Literal["top", "bottom"]

    def __init__(self, char: str, filled_part: Literal["top", "bottom"], shades: list[tuple[str, float]] | None = None):
        super().__init__(char, shades)
        self.filled_part = filled_part

    @timer
    def get_filled_color(self, section: ImageArray):
        ...

    @timer
    def likeness(self, visible_points, section_size) -> float:
        return visible_points.shape[0] / section_size if section_size else 0


class PolygonShape(Shape):
    """
    points
    ------
    Series of (x, y) values, together forming a polygon within which we
    will check the image pixels for being filled. The x and y values are
    relative: (0.0, 0.0) = top/left corner, (1.0, 1.0) = bottom right
    corner. Pixels outside this polygon will be checked for NOT being
    filled.
    """
    points: np.ndarray[tuple[int, int], np.dtype[np.float64]]

    @timer
    def __init__(
        self,
        char: str,
        points: np.ndarray[tuple[int, int], np.dtype[np.float64]],
        shades: list[tuple[str, float]] | None = None,
    ):
        super().__init__(char, shades)
        self.points = points
        self.path = Path(points, readonly=True, closed=True)
        self.area = self.get_area()

    @timer
    def get_area(self) -> float:
        # https://blog.finxter.com/5-best-ways-to-calculate-the-area-of-a-polygon-in-python/
        x, y = np.hsplit(self.points, 2)
        area = 0.5 * np.abs(np.dot(x.T, np.roll(y, 1)) - np.dot(y.T, np.roll(x, 1)))
        return area.sum()

    @timer
    def get_filled(self, section: ImageArray):
        # TODO: Continue ...
        affe = Affine2D().scale(section.shape[1], section.shape[0])
        path = self.path.transformed(affe)
        coords = np.indices((section.shape[1], section.shape[0])).transpose((2, 1, 0))
        coords2d = coords.reshape((section.shape[1] * section.shape[0], 2))
        contains = path.contains_points(coords2d)
        filled_coords = np.compress(contains, coords2d, axis=0)

    @timer
    def likeness(self, visible_points, section_size) -> float:
        """
        return: fraction of conforming points (inside / all) / shape area

        Returns fraction of filled points conforming to the shape.
        :param visible_points: List of (x, y) tuples for filled points
        :returns: Float from 0.0 to 1.0, where 1.0 is perfect likeness between
            image and shape
        """
        visible_point_count = visible_points.shape[0]
        filled_shape_points = section_size * self.area

        if visible_point_count:
            # Produces a list of booleans, telling us whether each of these
            # filled points is contained by the shape:
            containment = self.path.contains_points(visible_points)
            # Visible points inside shape:
            visible_match_count = containment.sum()
            # Visible points outside of shape:
            visible_miss_count = visible_point_count - visible_match_count
        else:
            # contains_points() can't handle an empty list
            visible_match_count = visible_miss_count = 0

        # Invisible points inside shape:
        invisible_miss_count = filled_shape_points - visible_match_count
        # Invisible points outside shape:
        invisible_match_count = section_size - visible_match_count - visible_miss_count - invisible_miss_count

        matches = visible_match_count + invisible_match_count
        misses = visible_miss_count + invisible_miss_count

        return float(matches - misses) / section_size


class ShapeSet(ABC):
    """
    Ordering of `polygons` is relevant for performance and outcomes; order them
    by which character you deem to be more desirable and/or probable.
    """
    SHORTHAND: ClassVar[str]
    FILLED: ClassVar[FilledShape]
    EMPTY: ClassVar[EmptyShape]
    BICOLORED: ClassVar[BiColorShape | None] = None
    POLYGONS: ClassVar[list[PolygonShape]] = []

    @classmethod
    def all(cls) -> list["Shape"]:
        return [cls.FILLED, cls.EMPTY, *cls.POLYGONS]

    @classmethod
    @timer
    def get_shape(cls, section: ImageArray, min_likeness: float):
        section_area = section.shape[0] * section.shape[1]
        # (array of y coords, array of x coords):
        nonzero = np.nonzero(section[:, :, Vi])
        filled = nonzero[0].size / section_area

        if filled < 0.05:
            # Micro-optimization 1
            return cls.EMPTY

        if filled > 0.95 or not cls.POLYGONS:
            # Micro-optimization 2
            return cls.BICOLORED or cls.FILLED

        # np.stack: combines `nonzero` into one array of (x, y) values.
        # Why + 0.5? The values in `nonzero` represent the upper left corners
        # of visible rectangular areas, but the shape objects will treat them
        # as _points_, and check if they fit inside of polygons. Adding 0.5 to
        # our coordinates places them in the middle of the areas instead.
        # Lastly, divide the (x, y) array by 2 integers, representing the
        # width and height of the section, thereby normalising it so its bounds
        # in both dimensions fit between 0 and 1, in order to make it
        # comparable with our path.
        visible_points = (
            (np.stack((nonzero[1], nonzero[0]), axis=1) + 0.5)
            / np.array((section.shape[1], section.shape[0]))
        )
        shapes: list[tuple[Shape, float]] = []

        for shape in cls.all():
            likeness = shape.likeness(visible_points, section_area)
            if likeness > min_likeness:
                return shape
            shapes.append((shape, likeness))

        return max(shapes, key=lambda c: c[1])[0]


class DefaultShapes(ShapeSet):
    SHORTHAND = "default"
    FILLED = FilledShape("$")
    EMPTY = EmptyShape(" ")
    POLYGONS = [
        PolygonShape(char="b", points=np.array(((0, 0), (1, 1), (0, 1), (0, 0)))),
        PolygonShape(char="d", points=np.array(((1, 0), (1, 1), (0, 1), (1, 0)))),
        PolygonShape(char="P", points=np.array(((0, 0), (1, 0), (0, 1), (0, 0)))),
        PolygonShape(char="?", points=np.array(((0, 0), (1, 0), (1, 1), (0, 0)))),
        PolygonShape(char="o", points=np.array(((0, 0.5), (1, 0.5), (1, 1), (0, 1), (0, 0.5)))),
        PolygonShape(char="*", points=np.array(((0, 0), (1, 0), (1, 0.5), (0, 0.5), (0, 0)))),
        PolygonShape(char=".", points=np.array(((0, 0.7), (1, 0.7), (1, 1), (0, 1), (0, 0.7)))),
        PolygonShape(char="°", points=np.array(((0, 0), (1, 0), (1, 0.3), (0, 0.3), (0, 0)))),
        # PolygonShape(char="b", points=np.array(((0, 0), (1, 1), (0, 1)))),
        # PolygonShape(char="d", points=np.array(((1, 0), (1, 1), (0, 1)))),
        # PolygonShape(char="P", points=np.array(((0, 0), (1, 0), (0, 1)))),
        # PolygonShape(char="?", points=np.array(((0, 0), (1, 0), (1, 1)))),
        # PolygonShape(char="o", points=np.array(((0, 0.5), (1, 0.5), (1, 1), (0, 1)))),
        # PolygonShape(char="*", points=np.array(((0, 0), (1, 0), (1, 0.5), (0, 0.5)))),
        # PolygonShape(char=".", points=np.array(((0, 0.7), (1, 0.7), (1, 1), (0, 1)))),
        # PolygonShape(char="°", points=np.array(((0, 0), (1, 0), (1, 0.3), (0, 0.3)))),
    ]


class SolidShapes(ShapeSet):
    SHORTHAND = "solid"
    FILLED = FilledShape("█", shades=[("░", 0), ("▒", 0.33), ("▓", 0.66)])
    EMPTY = EmptyShape(" ")
    POLYGONS = [
        # PolygonShape(char="▄", points=np.array(((0, 0.5), (1, 0.5), (1, 1), (0, 1), (0, 0.5)))),
        # PolygonShape(char="▀", points=np.array(((0, 0), (1, 0), (1, 0.5), (0, 0.5), (0, 0)))),
    ]
    BICOLORED = BiColorShape("▀", "top")
    """
    POLYGONS = [
        PolygonShape(char="🬿", points=np.array(((0, 1/4), (0, 1), (1, 1), (0, 1/4)))),
        PolygonShape(char="🭀", points=np.array(((0, 0), (0, 1), (0.5, 1), (0, 0)))),
        PolygonShape(char="🭋", points=np.array(((0.5, 1), (1, 1), (1, 0), (0.5, 1)))),
        PolygonShape(char="🭊", points=np.array(((0, 1), (1, 1), (1, 0.25), (0, 1)))),
        PolygonShape(char="🭚", points=np.array(((0, 0), (0, 0.75), (1, 1), (0, 0)))),
        PolygonShape(char="🭛", points=np.array(((0, 0), (0, 1), (0.5, 0), (0, 0)))),
        PolygonShape(char="🭥", points=np.array(((0, 0), (1, 1), (1, 0.75), (0, 0)))),
        PolygonShape(char="🭦", points=np.array(((0.5, 0), (1, 0), (1, 1), (0.5, 0)))),
        PolygonShape(char="▁", points=np.array(((0, 7 / 8), (1, 7 / 8), (1, 1), (0, 1), (0, 7/8)))),
        PolygonShape(char="▂", points=np.array(((0, 3 / 4), (1, 3 / 4), (1, 1), (0, 1), (0, 3/4)))),
        PolygonShape(char="▃", points=np.array(((0, 5 / 8), (1, 5 / 8), (1, 1), (0, 1), (0, 5/8)))),
        PolygonShape(char="▄", points=np.array(((0, 0.5), (1, 0.5), (1, 1), (0, 1), (0, 0.5)))),
        PolygonShape(char="▅", points=np.array(((0, 3 / 8), (1, 3 / 8), (1, 1), (0, 1), (0, 3/8)))),
        PolygonShape(char="▆", points=np.array(((0, 1 / 4), (1, 1 / 4), (1, 1), (0, 1), (0, 1/4)))),
        PolygonShape(char="▇", points=np.array(((0, 1 / 8), (1, 1 / 8), (1, 1), (0, 1), (0, 1/8)))),
        PolygonShape(char="🮂", points=np.array(((0, 0), (1, 0), (1, 1 / 4), (0, 1 / 4), (0, 0)))),
        PolygonShape(char="🮃", points=np.array(((0, 0), (1, 0), (1, 3 / 8), (0, 3 / 8), (0, 0)))),
        PolygonShape(char="▀", points=np.array(((0, 0), (1, 0), (1, 0.5), (0, 0.5), (0, 0)))),
        PolygonShape(char="🮄", points=np.array(((0, 0), (1, 0), (1, 5 / 8), (0, 5 / 8), (0, 0)))),
        PolygonShape(char="🮅", points=np.array(((0, 0), (1, 0), (1, 3 / 4), (0, 3 / 4), (0, 0)))),
        PolygonShape(char="🮆", points=np.array(((0, 0), (1, 0), (1, 7 / 8), (0, 7 / 8), (0, 0)))),
        PolygonShape(char="▌", points=np.array(((0, 0), (1, 0), (1, 0.5), (0, 0.5), (0, 0)))),
        PolygonShape(char="▐", points=np.array(((0, 0.5), (0, 1), (1, 1), (1, 0.5), (0, 0.5)))),
    ]
    """
