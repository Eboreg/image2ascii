from typing import Literal, TypeVar

import numpy as np


ImageArray = np.ndarray[tuple[int, int, Literal[5]], np.dtype[np.uint8]]

RGBA = np.ndarray[tuple[Literal[4]], np.dtype[np.uint8]]

NumberT = TypeVar("NumberT", float, int, covariant=True)
