import dataclasses
from typing import TYPE_CHECKING, Protocol


if TYPE_CHECKING:
    from image2ascii.color import Color
    from image2ascii.geometry import Shape


class HasBackground(Protocol):
    background: "Color | None"


class OutputAtom: ...


class Character(OutputAtom):
    def __init__(
        self,
        shape: "Shape",
        column: int,
        row: int,
        color: "Color | None",
        background: "Color | None",
        opacity: float = 1,
    ):
        self.char = shape.char_for_opacity(opacity)
        self.shape = shape
        self.column = column
        self.row = row
        self.color = color
        self.background = background


@dataclasses.dataclass
class ColorStart(OutputAtom):
    color: "Color"
    column: int
    row: int


@dataclasses.dataclass
class ColorEnd(OutputAtom):
    color: "Color"
    column: int
    row: int


@dataclasses.dataclass
class BackgroundStart(OutputAtom):
    color: "Color"
    column: int
    row: int


@dataclasses.dataclass
class BackgroundEnd(OutputAtom):
    color: "Color"
    column: int
    row: int


@dataclasses.dataclass
class Linebreak(OutputAtom):
    old_row: int
    new_row: int


@dataclasses.dataclass
class RowStart(OutputAtom):
    row: int
    background: "Color | None" = None


@dataclasses.dataclass
class RowEnd(OutputAtom):
    row: int
    background: "Color | None" = None


@dataclasses.dataclass
class OutputStart(OutputAtom):
    background: "Color | None" = None


@dataclasses.dataclass
class OutputEnd(OutputAtom):
    background: "Color | None" = None
