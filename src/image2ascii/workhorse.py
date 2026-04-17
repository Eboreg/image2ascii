from os import PathLike
from pathlib import Path
from typing import IO, TYPE_CHECKING, Any, Generator, Self

import numpy as np

from image2ascii.character import Character
from image2ascii.geometry import OptionalPointF, PositionedBoxF, Size, SizeF, SubRect2
from image2ascii.geometry.rect import SubRectF2
from image2ascii.image import ImagePlus
from image2ascii.registry import Registry
from image2ascii.timing import timer
from image2ascii.types import ImageArray


if TYPE_CHECKING:
    from image2ascii.color_converters import AbstractColorConverter
    from image2ascii.config import Config
    from image2ascii.geometry import PositionedBoxPartition, ShapeSet, PointF
    from image2ascii.renderers import AbstractRenderer


class Workhorse:
    config: "Config"
    image: ImagePlus
    original_image: ImagePlus
    color_converter: "AbstractColorConverter"
    shapeset: type["ShapeSet"]
    is_image_pixelmapped: bool = False
    visible_cropbox: SubRect2 | None = None

    @property
    def final_size_chars_f(self) -> SizeF:
        """Final number of columns & rows of the ASCII output"""
        return self.config.viewport_size.fit_ratio(self.image.ratio / self.config.char_ratio)

    @property
    def final_size_chars(self) -> Size:
        return self.final_size_chars_f.to_size(round_for_ratio=True)

    @property
    def final_size_px_f(self) -> SizeF:
        """
        Final size the image will have before being converted to ASCII:
        - width = number of output columns * quality
        - height = number of output rows * quality / character w/h ratio
        """
        return self.final_size_chars_f * self.config.quality / SizeF(1, self.config.char_ratio)

    @property
    def final_size_px(self) -> Size:
        return self.final_size_px_f.to_size(round_for_ratio=True)

    @timer
    def __init__(
        self,
        image: ImagePlus,
        config: "Config",
        color_converter: "AbstractColorConverter | None" = None,
        shapeset: "type[ShapeSet] | None" = None,
    ):
        self.config = config
        self.color_converter = color_converter or config.color_converter()
        self.shapeset = shapeset or config.shapeset
        self.original_image = image
        self.image = image.copy()
        self.plugins = Registry(config)

    @timer
    def generate(self) -> Generator[Character, Any, None]:
        matrix = self.image.get_matrix(regenerate_if_stale=True)

        if self.is_image_pixelmapped:
            columns, rows = self.image.size.tuple
        else:
            columns, rows = self.final_size_chars_f.to_size().tuple

        for box in self.image.size.partition(columns, rows):
            yield self.__get_character(matrix, box)

    @timer
    def __calculate_visibility(self, image: ImagePlus):
        # First check if we should determine visibility by background colour
        # (dis-)similarity:
        if self.config.background and self.config.transparency.use_bgdistance(bool(self.config.background)):
            image.update_visibility_by_bgdistance(self.config.background, self.config.transparency.bg_distance)

        # Maybe we should let "perceived brightness" do its thing:
        if self.config.transparency.use_brightness(bool(self.config.background)):
            image.update_visibility_by_brightness(self.config.transparency.brightness)

        # Check if there are literally transparent pixels:
        if self.config.transparency.use_alpha():
            image.update_visibility_by_alpha(self.config.transparency.alpha)

    def zoom(self, factor: float, center: "PointF | None" = None):
        import ipdb; ipdb.set_trace()
        image = self.original_image.copy()
        size = image.size
        cropbox = SubRectF2(image.size)
        if self.visible_cropbox:
            cropbox += self.visible_cropbox * image.size
            size = cropbox.size
        fitted_size = size.fit_inside(self.config.viewport_size_px)
        zoomed_size = fitted_size * factor
        resized_viewport = self.config.viewport_size_px.fit_outside(size) * (1 / factor)
        cropbox += size.crop(resized_viewport, center).to_subrect(round_for_ratio=True)
        image.crop(cropbox.to_subrect(round_for_ratio=True))

        # fitted_size *= factor
        # center = center or (0.5, 0.5)
        # box = PositionedBoxF(fitted_size, self.config.viewport_size_px).zoom(factor).place_relatively(center)
        # cropbox after image is cropped to `cropbox` and resized by `factor`:
        # zoomed_cropbox = box.visible_box
        # box2 = PositionedBoxF(size, self.config.viewport_size_px).place_relatively(center)

    @timer
    def prepare(self):
        """
        1. Resize to final_size_px
        2. Convert to RGBA
        3. Enhance
        4. Calculate matrix visibility from config
        5. Crop away transparent; keep cropbox
        6. Final resize:
            a. If has invisibility: resize to final_size_px again if needed
            b. Else: resize to one pixel per output character

        Zoom (using same object, with previously displayed image):
        1. Calculate visible box from cropbox above + scale + x, y
        2. From original image, crop to visible box
        3. Resize to final_size_px
        4. Enhance
        """
        self.is_image_pixelmapped = False
        self.image.resize(self.final_size_px)  # 1
        self.image.convert_to_rgba()  # 2
        self.image.enhance(  # 3
            brightness=self.config.brightness,
            color_balance=self.config.color_balance,
            contrast=self.config.contrast,
            sharpness=self.config.sharpness,
            invert=self.config.invert,
        )
        self.__calculate_visibility(self.image)  # 4

        if self.config.crop:  # 5
            self.visible_cropbox = self.image.get_visible_cropbox(regenerate_matrix_if_stale=True)
            self.image.crop(self.visible_cropbox)
            if self.image.is_matrix_stale:
                self.__calculate_visibility(self.image)

        if not self.image.has_invisibility(regenerate_matrix_if_stale=True):
            self.image.resize(self.final_size_chars)  # 6a
            self.is_image_pixelmapped = True
        else:
            self.image.resize(self.final_size_px)  # 6b
            if self.image.is_matrix_stale:
                self.__calculate_visibility(self.image)

    def prepare_and_render(self, renderer: "AbstractRenderer"):
        self.prepare()
        self.render(renderer)

    @timer
    def render(self, renderer: "AbstractRenderer"):
        renderer.start(
            original_ratio=self.final_size_px_f.ratio,
            size_chars=self.final_size_chars_f,
            background=self.color_converter.closest(self.config.background) if self.config.background else None,
        )
        for character in self.generate():
            renderer.render_character(character)
        renderer.finish()

    @timer
    def __get_character(self, matrix: ImageArray, box: "PositionedBoxPartition") -> Character:
        section = matrix[box.top : box.bottom, box.left : box.right]
        section_area = section.shape[0] * section.shape[1]

        if self.is_image_pixelmapped:
            char = self.shapeset.FILLED.char
        else:
            # (array of y coords, array of x coords):
            nonzero = np.nonzero(section[:, :, -1])
            filled = nonzero[0].size / section_area

            if filled < 0.05:
                # Micro-optimization 1
                char = self.shapeset.EMPTY.char
            elif filled > 0.95:
                # Micro-optimization 2
                char = self.shapeset.FILLED.char
            else:
                # The values in `nonzero` represent the upper left corners
                # of visible rectangular areas, but the shape objects will
                # treat them as _points_, and check if they fit inside of
                # polygons. Adding 0.5 to our coordinates places them in
                # the middle of the areas instead.
                visible_points = (
                    (np.stack((nonzero[1], nonzero[0]), axis=1) + 0.5)
                    / np.array((section.shape[1], section.shape[0]))
                )
                char = self.shapeset.get_shape(visible_points, section_area, self.config.min_likeness).char

        return Character(
            char=char,
            column=box.column,
            row=box.row,
            color=(
                self.color_converter.get_section_color(section, self.config.color_inference) or
                self.config.default_color
            ),
        )

    @classmethod
    @timer
    def load(cls, file: str | bytes | PathLike | Path | IO[bytes], config: "Config | None" = None) -> Self:
        from image2ascii.config import Config

        return cls(ImagePlus.load(file), config or Config())

    @classmethod
    @timer
    def load_svg(cls, file: str | bytes | PathLike | Path | IO[bytes], config: "Config | None" = None) -> Self:
        from image2ascii.config import Config

        config = config or Config()

        return cls(ImagePlus.load_svg(file, output_size=config.viewport_size_px), config)
