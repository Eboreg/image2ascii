import hashlib
from decimal import Decimal
from fractions import Fraction
from os import PathLike
from typing import TYPE_CHECKING

from PIL import Image

from image2ascii.timing import timer


if TYPE_CHECKING:
    from _typeshed import SupportsRichComparisonT


@timer
def find_closest_multiple(
    value: float | Decimal,
    multiplier: int,
    maximum: int | None = None,
    grow: bool = True,
) -> int:
    if not isinstance(value, Decimal):
        value = Decimal(value)

    if maximum is not None:
        maximum -= maximum % multiplier

    remainder = value % multiplier
    result = int(value - remainder)

    if grow and remainder:
        result += multiplier

    return min(result, maximum) if maximum is not None else result


def hash_file(path: PathLike) -> str:
    sha256 = hashlib.sha256()

    with open(path, "rb") as file:
        while chunk := file.read(65536):
            sha256.update(chunk)

    return sha256.hexdigest()


def hash_image(image: Image.Image) -> str:
    sha256 = hashlib.sha256(image.tobytes())
    return sha256.hexdigest()


def min_nullable(*values: "SupportsRichComparisonT | None") -> "SupportsRichComparisonT":
    value_list = [v for v in values if v is not None]
    if len(value_list) == 0:
        raise TypeError
    if len(value_list) == 1:
        return value_list[0]
    return min(value_list)


@timer
def partition(value: int, num_parts: int):
    """
    Divides `value` in `num_parts` parts in such a way that each part is an
    integer and any division remainder is distributed evenly across the result.
    The last part is guaranteed to be > 0 as long as `value` >= 1.

    Ex:
    >>> partition(100, 6)
    [16, 17, 17, 16, 17, 17]
    """
    if value % num_parts == 0:
        return [int(value / num_parts)] * num_parts

    if value - 1 < num_parts / 2:
        part_size = Fraction(value - 1, num_parts)
    else:
        part_size = Fraction(value, num_parts)

    result: list[int] = []
    part_size_int = int(part_size)

    for idx in range(num_parts):
        part = part_size_int
        if value - 1 < num_parts / 2 and idx == num_parts - 1:
            part += 1
        if idx * part_size > sum(result):
            part += 1

        result.append(part)

    assert sum(result) == value, f"sum(result) should be {value} but is {sum(result)}"
    assert len(result) == num_parts, f"len(result) should be {num_parts} but is {len(result)}"

    return result
