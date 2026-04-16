from io import BytesIO, IOBase
from os import PathLike
from pathlib import Path
from typing import IO, Self, cast

import cairosvg
import numpy as np
from PIL import Image, ImageEnhance, ImageOps
from PIL.Image import Resampling

from image2ascii.color import A, B, Color, G, R, Vi, get_perceived_brightness
from image2ascii.geometry import AbstractSize, Size, SubRect, SubRect2
from image2ascii.timing import timer
from image2ascii.types import ImageArray


class ImagePlus:
    __image: Image.Image
    __matrix: ImageArray | None = None

    is_matrix_stale: bool = False

    def __init__(self, image: Image.Image, matrix: ImageArray | None = None):
        self.__image = image
        self.__matrix = matrix

    @property
    def ratio(self):
        return self.__image.width / self.__image.height

    @property
    def size(self):
        return Size.i(self.__image)

    def __apply_enhance(
        self,
        Enhance: type[ImageEnhance.Brightness | ImageEnhance.Contrast | ImageEnhance.Sharpness | ImageEnhance.Color],
        value: float,
    ):
        if value != 1.0:
            self.__image = Enhance(self.__image).enhance(value)
            self.is_matrix_stale = True

    @timer
    def apply_brightness(self, value: float):
        self.__apply_enhance(ImageEnhance.Brightness, value)

    @timer
    def apply_color_balance(self, value: float):
        self.__apply_enhance(ImageEnhance.Color, value)

    @timer
    def apply_contrast(self, value: float):
        self.__apply_enhance(ImageEnhance.Contrast, value)

    @timer
    def apply_sharpness(self, value: float):
        self.__apply_enhance(ImageEnhance.Sharpness, value)

    @timer
    def as_nparray(self):
        return np.asarray(self.__image)

    @timer
    def convert_to_rgba(self):
        if self.__image.mode != "RGBA":
            self.__image = self.__image.convert("RGBA")

    @timer
    def copy(self):
        return ImagePlus(self.__image.copy(), self.__matrix)

    @timer
    def crop(self, box: tuple[int, int, int, int] | SubRect | SubRect2):
        if isinstance(box, tuple):
            box = SubRect(*box)
        if any(box.tuple):
            self.__image = self.__image.crop(box.tuple)
            if not self.is_matrix_stale:
                self.__matrix = self.get_matrix(regenerate_if_stale=False)[box.upper:box.lower, box.left:box.right]

    @timer
    def enhance(
        self,
        brightness: float = 1.0,
        color_balance: float = 1.0,
        contrast: float = 1.0,
        sharpness: float = 1.0,
        invert: bool = False,
    ):
        self.apply_brightness(brightness)
        self.apply_color_balance(color_balance)
        self.apply_contrast(contrast)
        self.apply_sharpness(sharpness)
        if invert:
            self.invert()

    @timer
    def get_matrix(self, regenerate_if_stale: bool) -> ImageArray:
        if regenerate_if_stale and self.is_matrix_stale:
            return self.regenerate_matrix()
        return self.__matrix if self.__matrix is not None else self.regenerate_matrix()

    @timer
    def get_visible_cropbox(self, regenerate_matrix_if_stale: bool):
        matrix = self.get_matrix(regenerate_if_stale=regenerate_matrix_if_stale)
        return SubRect2.from_visible(matrix)

    @timer
    def has_invisibility(self, regenerate_matrix_if_stale: bool) -> bool:
        matrix = self.get_matrix(regenerate_if_stale=regenerate_matrix_if_stale)
        return not np.all(matrix[:, :, Vi])

    @timer
    def invert(self):
        lut = list(range(0xFF, -1, -1)) * 3 + list(range(0xFF + 1))
        self.__image = self.__image.point(lut)
        self.is_matrix_stale = True

    @timer
    def regenerate_matrix(self) -> ImageArray:
        # 3-axis matrix: 5 colour parameters (R, G, B, A, Vi) for each
        # pixel. Init them with ones so the transparency checks can AND
        # them away for the Vi values later.
        matrix = cast(ImageArray, np.ones((self.__image.height, self.__image.width, 5), dtype=np.uint8))

        # Fill first 4 values with R, G, B, A
        matrix[:, :, : A + 1] = self.as_nparray()

        self.__matrix = matrix
        self.is_matrix_stale = False

        return matrix

    @timer
    def resize(self, size: Size | tuple[int, int] | list[int], resample: Resampling | None = None):
        if isinstance(size, Size):
            size = size.tuple
        if size != (self.__image.width, self.__image.height):
            self.__image = self.__image.resize(size, resample=resample)
            self.is_matrix_stale = True

    @timer
    def update_visibility_by_bgdistance(self, background: Color, min_distance: int):
        if min_distance > 0:
            matrix = self.get_matrix(regenerate_if_stale=True)
            colors = matrix.reshape((matrix.shape[0] * matrix.shape[1], 5)).astype(np.int64)
            distances = background.get_distances(colors).reshape((matrix.shape[0], matrix.shape[1]))
            matrix[:, :, Vi] &= distances >= min_distance
            self.__matrix = matrix

    @timer
    def update_visibility_by_brightness(self, min_brightness: int):
        if min_brightness > 0:
            matrix = self.get_matrix(regenerate_if_stale=True)
            perceived_brightness = get_perceived_brightness(matrix[:, :, R], matrix[:, :, G], matrix[:, :, B])
            matrix[:, :, Vi] &= perceived_brightness >= min_brightness
            self.__matrix = matrix

    @timer
    def update_visibility_by_alpha(self, min_alpha: int):
        if min_alpha > 0:
            matrix = self.get_matrix(regenerate_if_stale=True)
            matrix[:, :, Vi] &= matrix[:, :, A] >= min_alpha
            self.__matrix = matrix

    @classmethod
    @timer
    def load(cls, file: str | bytes | PathLike | Path | IO[bytes]) -> Self:
        if isinstance(file, Path):
            file = str(file)

        with Image.open(file) as image:
            image.load()
            ImageOps.exif_transpose(image, in_place=True)

        return cls(image)

    @classmethod
    @timer
    def load_svg(
        cls,
        file: str | bytes | PathLike | Path | IO[bytes],
        output_size: AbstractSize | None = None,
        output_width: float | None = None,
        output_height: float | None = None,
    ) -> Self:
        output = BytesIO()
        if output_size is not None:
            output_width, output_height = output_size.tuple
        kwargs = {
            "output_width": output_width,
            "output_height": output_height,
            "write_to": output,
        }

        if isinstance(file, bytes):
            kwargs["bytestring"] = file
        elif isinstance(file, IOBase):
            kwargs["file_obj"] = file
        else:
            kwargs["url"] = str(file)

        cairosvg.svg2png(**kwargs)
        return cls.load(output)
