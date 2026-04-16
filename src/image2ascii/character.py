import dataclasses
from typing import TYPE_CHECKING


if TYPE_CHECKING:
    from image2ascii.color import Color


@dataclasses.dataclass
class Character:
    char: str
    column: int
    row: int
    color: "Color | None" = None
