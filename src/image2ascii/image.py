from io import BytesIO, IOBase
from os import PathLike
from pathlib import Path
from typing import IO, TYPE_CHECKING, Self, cast

import cairosvg
import numpy as np
from PIL import Image, ImageEnhance, ImageOps
from PIL.Image import Resampling

from image2ascii.color import ANSI_COLOR_DICT, A, B, Color, G, R, Vi, get_perceived_brightness
from image2ascii.geometry import Size, SubRect
from image2ascii.timing import timer
from image2ascii.types import ImageArray


if TYPE_CHECKING:
    from image2ascii.geometry import SizeF


EnhanceType = type[ImageEnhance.Brightness | ImageEnhance.Contrast | ImageEnhance.Sharpness | ImageEnhance.Color]


class ImagePlus:
    """
    is_image_opaque
    ---------------
    It means the image has no pixels that will be treated as "invisible"
    (calculated from their colour, brightness, and/or alpha). This enables the
    following optimizations:

    * We know all rendered characters will be `self.shapeset.FILLED`, so we
      don't need to waste time analysing the "shape" of each section.
    * We can (and will!) resize the source image in such a way that each
      pixel represents one output character.

    pixel_ratio
    -----------
    It is set to the inverse (1 / x) of Config.char_ratio when the image is
    asymmetrically resized to compensate for said char_ratio. The point is for
    the two ratios to then cancel each other out.
    """
    __image: Image.Image
    __matrix: ImageArray | None = None

    is_matrix_stale: bool = True
    is_opaque: bool | None = None  # Yes/no/unknown
    pixel_ratio: float = 1

    def __init__(self, image: Image.Image, matrix: ImageArray | None = None, is_opaque: bool | None = None):
        self.__image = image
        self.is_opaque = is_opaque
        if matrix is not None:
            self.__matrix = matrix
            self.is_matrix_stale = False

    @property
    def ratio(self) -> float:
        return self.__image.width / self.__image.height

    @property
    def size(self) -> Size:
        return Size(self.__image.width, self.__image.height)

    @timer
    def as_nparray(self):
        self.convert_to_rgba()
        return np.asarray(self.__image)

    @timer
    def convert_to_rgba(self):
        if self.__image.mode != "RGBA":
            self.__image = self.__image.convert("RGBA")

    @timer
    def copy(self):
        return ImagePlus(
            image=self.__image.copy(),
            matrix=self.__matrix.copy() if self.__matrix is not None else None,
            is_opaque=self.is_opaque,
        )

    @timer
    def crop(self, box: SubRect):
        if box:
            self.__image = self.__image.crop(box.crop_tuple)
            if not self.is_matrix_stale:
                self.__matrix = self.get_matrix(regenerate_if_stale=False)[box.top:box.bottom, box.left:box.right]
                self.is_opaque = bool(np.all(self.__matrix[:, :, Vi]))
            else:
                # If it was flagged as opaque, it will remain so after a
                # crop, so don't touch is_opaque in that case. If, on the other
                # hand, it was flagged as _not_ opaque, we don't yet know if
                # that is still the case (all the transparent parts may have
                # been cropped away).
                if not self.is_opaque:
                    self.is_opaque = None

    def enhance(
        self,
        brightness: float = 1.0,
        color_balance: float = 1.0,
        contrast: float = 1.0,
        sharpness: float = 1.0,
        invert: bool = False,
    ):
        self.__apply_enhance(ImageEnhance.Brightness, brightness)
        self.__apply_enhance(ImageEnhance.Color, color_balance)
        self.__apply_enhance(ImageEnhance.Contrast, contrast)
        self.__apply_enhance(ImageEnhance.Sharpness, sharpness)
        if invert:
            self.invert()

    @timer
    def fill_transparency(self, fill: Color | None = None):
        """
        All pixels with alpha < 0xff will be filled with `fill` in reverse
        proportion to how high their alpha value is. This is because pixels
        with very low alpha values sometimes get very weird colour data.
        """
        fill = fill or ANSI_COLOR_DICT["BLACK"]
        matrix = self.get_matrix(regenerate_if_stale=True)
        alpha_fractions = matrix[:, :, A].repeat(3).reshape((matrix.shape[0], matrix.shape[1], 3)) / 0xff
        original = matrix[:, :, :A] * alpha_fractions
        filled = fill.array[:A] * (1 - alpha_fractions)
        matrix[:, :, :A] = (original + filled).astype(np.uint8)
        self.__matrix = matrix

    def get_matrix(self, regenerate_if_stale: bool) -> ImageArray:
        if regenerate_if_stale and self.is_matrix_stale:
            return self.regenerate_matrix()
        return self.__matrix if self.__matrix is not None else self.regenerate_matrix()

    @timer
    def get_visible_cropbox(self, regenerate_matrix_if_stale: bool):
        matrix = self.get_matrix(regenerate_if_stale=regenerate_matrix_if_stale)
        return SubRect.from_visible(matrix)

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
        self.is_opaque = True

        return matrix

    @timer
    def resize(self, size: Size | tuple[int, int] | list[int], resample: Resampling | None = None):
        if isinstance(size, Size):
            size = size.tuple
        if size != (self.__image.width, self.__image.height):
            self.__image = self.__image.resize(size, resample=resample)
            self.is_matrix_stale = True

    @timer
    def update_visibility_by_alpha(self, min_alpha: int):
        if min_alpha > 0:
            matrix = self.get_matrix(regenerate_if_stale=True)
            self.__update_visibility(matrix, matrix[:, :, A] >= min_alpha)

    @timer
    def update_visibility_by_bgdistance(self, background: Color, min_distance: int):
        if min_distance > 0:
            matrix = self.get_matrix(regenerate_if_stale=True)
            colors = matrix.reshape((matrix.shape[0] * matrix.shape[1], 5)).astype(np.int64)
            distances = background.get_distances(colors).reshape((matrix.shape[0], matrix.shape[1]))
            self.__update_visibility(matrix, distances >= min_distance)

    @timer
    def update_visibility_by_brightness(self, min_brightness: int):
        if min_brightness > 0:
            matrix = self.get_matrix(regenerate_if_stale=True)
            perceived_brightness = get_perceived_brightness(matrix[:, :, R], matrix[:, :, G], matrix[:, :, B])
            self.__update_visibility(matrix, perceived_brightness >= min_brightness)

    @timer
    def __apply_enhance(self, Enhance: EnhanceType, value: float):
        if value != 1.0:
            self.__image = Enhance(self.__image).enhance(value)
            self.is_matrix_stale = True
            self.is_opaque = None

    @timer
    def __update_visibility(self, matrix: ImageArray, visibility: np.ndarray[tuple[int, int], np.dtype[np.bool]]):
        matrix[:, :, Vi] &= visibility
        self.is_opaque = bool(np.all(matrix[:, :, Vi]))
        self.is_matrix_stale = False
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
        output_size: "SizeF | None" = None,
        output_width: float | None = None,
        output_height: float | None = None,
    ) -> Self:
        output = BytesIO()
        if output_size is not None:
            output_width, output_height = output_size.tuple
        kwargs: dict = {
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
