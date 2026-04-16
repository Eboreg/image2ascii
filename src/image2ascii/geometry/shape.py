from abc import ABC, abstractmethod
from typing import ClassVar

import numpy as np
from matplotlib.path import Path

from image2ascii.timing import timer


class AbstractShape(ABC):
    char: str
    area: float

    @abstractmethod
    def likeness(self, visible_points: np.ndarray[tuple[int, int], np.dtype[np.float64]], section_size: int) -> float:
        ...


class FilledShape(AbstractShape):
    """
    A completely filled shape, which means the likeness with any given
    boolmatrix is just the fraction of its members that are True.
    """
    area = 1.0

    def __init__(self, char: str):
        self.char = char

    @timer
    def likeness(self, visible_points, section_size) -> float:
        # Let's just let division by 0 raise its exception
        return visible_points.shape[0] / section_size


class EmptyShape(AbstractShape):
    """
    A completely empty shape, which means the likeness with any given
    boolmatrix is just the fraction of its members that are False.
    """
    area = 0.0

    def __init__(self, char: str):
        self.char = char

    @timer
    def likeness(self, visible_points, section_size) -> float:
        return (section_size - visible_points.shape[0]) / section_size


class PolygonShape(AbstractShape):
    @timer
    def __init__(self, char: str, points: np.ndarray[tuple[int, int], np.dtype[np.float64]]):
        """
        :param points: Series of (x, y) values, together forming a polygon
            within which we will check the image pixels for being filled. The
            x and y values are relative: (0.0, 0.0) = top/left corner,
            (1.0, 1.0) = bottom right corner. Pixels outside this polygon will
            be checked for NOT being filled.
        """
        self.char = char
        self.points = points
        self.path = Path(points, readonly=True)
        self.area = self.get_area()

    @timer
    def get_area(self) -> float:
        # https://blog.finxter.com/5-best-ways-to-calculate-the-area-of-a-polygon-in-python/
        x, y = np.hsplit(self.points, 2)
        area = 0.5 * np.abs(np.dot(x.T, np.roll(y, 1)) - np.dot(y.T, np.roll(x, 1)))
        return area.sum()

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
    POLYGONS: ClassVar[list[PolygonShape]]

    @classmethod
    def all(cls) -> list["AbstractShape"]:
        return [cls.FILLED, cls.EMPTY, *cls.POLYGONS]

    @classmethod
    @timer
    def get_shape(
        cls,
        visible_points: np.ndarray[tuple[int, int], np.dtype[np.float64]],
        section_area: int,
        min_likeness: float,
    ) -> AbstractShape:
        shapes: list[tuple[AbstractShape, float]] = []

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
        PolygonShape(char="b", points=np.array(((0, 0), (1, 1), (0, 1)))),
        PolygonShape(char="d", points=np.array(((1, 0), (1, 1), (0, 1)))),
        PolygonShape(char="P", points=np.array(((0, 0), (1, 0), (0, 1)))),
        PolygonShape(char="?", points=np.array(((0, 0), (1, 0), (1, 1)))),
        PolygonShape(char="o", points=np.array(((0, 0.5), (1, 0.5), (1, 1), (0, 1)))),
        PolygonShape(char="*", points=np.array(((0, 0), (1, 0), (1, 0.5), (0, 0.5)))),
        PolygonShape(char=".", points=np.array(((0, 0.7), (1, 0.7), (1, 1), (0, 1)))),
        PolygonShape(char="°", points=np.array(((0, 0), (1, 0), (1, 0.3), (0, 0.3)))),
    ]


class SolidShapes(ShapeSet):
    SHORTHAND = "solid"
    FILLED = FilledShape("█")
    EMPTY = EmptyShape(" ")
    POLYGONS = [
        PolygonShape(char="🬿", points=np.array(((0, 1 / 4), (0, 1), (1, 1)))),
        PolygonShape(char="🭀", points=np.array(((0, 0), (0, 1), (0.5, 1)))),
        PolygonShape(char="🭋", points=np.array(((0.5, 1), (1, 1), (1, 0)))),
        PolygonShape(char="🭊", points=np.array(((0, 1), (1, 1), (1, 0.25)))),
        PolygonShape(char="🭚", points=np.array(((0, 0), (0, 0.75), (1, 1)))),
        PolygonShape(char="🭛", points=np.array(((0, 0), (0, 1), (0.5, 0)))),
        PolygonShape(char="🭥", points=np.array(((0, 0), (1, 1), (1, 0.75)))),
        PolygonShape(char="🭦", points=np.array(((0.5, 0), (1, 0), (1, 1)))),
        PolygonShape(char="▁", points=np.array(((0, 7 / 8), (1, 7 / 8), (1, 1), (0, 1)))),
        PolygonShape(char="▂", points=np.array(((0, 3 / 4), (1, 3 / 4), (1, 1), (0, 1)))),
        PolygonShape(char="▃", points=np.array(((0, 5 / 8), (1, 5 / 8), (1, 1), (0, 1)))),
        PolygonShape(char="▄", points=np.array(((0, 0.5), (1, 0.5), (1, 1), (0, 1)))),
        PolygonShape(char="▅", points=np.array(((0, 3 / 8), (1, 3 / 8), (1, 1), (0, 1)))),
        PolygonShape(char="▆", points=np.array(((0, 1 / 4), (1, 1 / 4), (1, 1), (0, 1)))),
        PolygonShape(char="▇", points=np.array(((0, 1 / 8), (1, 1 / 8), (1, 1), (0, 1)))),
        PolygonShape(char="🮂", points=np.array(((0, 0), (1, 0), (1, 1 / 4), (0, 1 / 4)))),
        PolygonShape(char="🮃", points=np.array(((0, 0), (1, 0), (1, 3 / 8), (0, 3 / 8)))),
        PolygonShape(char="▀", points=np.array(((0, 0), (1, 0), (1, 0.5), (0, 0.5)))),
        PolygonShape(char="🮄", points=np.array(((0, 0), (1, 0), (1, 5 / 8), (0, 5 / 8)))),
        PolygonShape(char="🮅", points=np.array(((0, 0), (1, 0), (1, 3 / 4), (0, 3 / 4)))),
        PolygonShape(char="🮆", points=np.array(((0, 0), (1, 0), (1, 7 / 8), (0, 7 / 8)))),
        PolygonShape(char="▌", points=np.array(((0, 0), (1, 0), (1, 0.5), (0, 0.5)))),
        PolygonShape(char="▐", points=np.array(((0, 0.5), (0, 1), (1, 1), (1, 0.5)))),
    ]
