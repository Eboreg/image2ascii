from collections.abc import Iterator
from os import PathLike
from pathlib import Path
from typing import IO, TYPE_CHECKING, Self

import numpy as np

from image2ascii.character import Character
from image2ascii.geometry import SizeF, SubRectF
from image2ascii.image import ImagePlus
from image2ascii.registry import Registry
from image2ascii.timing import timer
from image2ascii.types import ImageArray


if TYPE_CHECKING:
    from image2ascii.color_converters import AbstractColorConverter
    from image2ascii.config import Config
    from image2ascii.geometry import IndexedSizePartition, PointF, ShapeSet, Size, SubRect
    from image2ascii.renderers import AbstractRenderer


class Workhorse:
    """
    is_whole_image_opaque
    ---------------------
    This is used for a micro-optimization: If the whole image was found to be
    opaque, we know that all possible parts of it also are, so zoom() doesn't
    even need to check that. See also comments in image.py.
    """
    color_converter: "AbstractColorConverter"
    config: "Config"
    image: ImagePlus
    is_whole_image_opaque: bool = False
    original_image: ImagePlus
    shapeset: type["ShapeSet"]
    visible_cropbox: "SubRect | None" = None

    @property
    def final_size_chars_f(self) -> SizeF:
        """Final number of columns & rows of the ASCII output"""
        return self.config.viewport_size.to_size_f().fit_ratio(
            self.image.ratio / self.config.char_ratio / self.image.pixel_ratio
        )

    @property
    def final_size_chars(self) -> "Size":
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
    def final_size_px(self) -> "Size":
        return self.final_size_px_f.to_size(round_for_ratio=True)

    @timer
    def __init__(
        self,
        image: ImagePlus,
        config: "Config",
        color_converter: "AbstractColorConverter | None" = None,
        shapeset: "type[ShapeSet] | None" = None,
    ):
        self.config = config.model_copy()
        self.color_converter = color_converter or config.color_converter()
        self.shapeset = shapeset or config.shapeset
        self.original_image = image
        self.image = image.copy()
        self.plugins = Registry(config)

    @timer
    def generate(self) -> Iterator[Character]:
        matrix = self.image.get_matrix(regenerate_if_stale=True)

        if self.image.is_opaque:
            columns, rows = self.image.size.tuple
        else:
            columns, rows = self.final_size_chars.tuple

        for rect in self.image.size.partition(columns, rows):
            yield self.__get_character(matrix, rect)

    @timer
    def prepare(self):
        """
        1. Resize to final_size_px
        2. Enhance
        3. Calculate matrix visibility from config. This data will probably be
           destroyed by later operations, but we need it in order to know if
           the image is opaque.
        4. Crop away invisible "borders" if desired; keep cropbox for later (se
           zoom())
        5. If the image was found to be opaque:
           5.1. Resize to 1px per output character
           5.2. Set image.pixel_ratio (see comment in image.py)
           5.3. Fill transparent and semi-transparent pixels with a mix of
              their original colour and background colour (see comments in
              this function)
        6. Otherwise:
           6.1. Resize to final size
           6.2. Recalculate matrix visibility; this is necessary because a
              resize flags the matrix as stale, and therefore it will get
              regenerated next time it's needed, and will then not have any
              visibility info.
        """
        self.image.resize(self.final_size_px)  # 1
        self.__enhance(self.image)  # 2
        self.__update_visibility(self.image)  # 3

        if self.config.crop:  # 4
            self.visible_cropbox = self.image.get_visible_cropbox(regenerate_matrix_if_stale=True)
            self.image.crop(self.visible_cropbox)

        if self.image.is_opaque:
            self.is_whole_image_opaque = True
            self.image.resize(self.final_size_chars)  # 5.1
            self.image.pixel_ratio = 1 / self.config.char_ratio  # 5.2
            self.image.fill_transparency(self.config.background)  # 5.3
        else:
            self.is_whole_image_opaque = False
            self.image.resize(self.final_size_px)  # 6.1
            if self.image.is_matrix_stale:
                self.__update_visibility(self.image)  # 6.2

    def prepare_and_render(self, renderer: "AbstractRenderer"):
        self.prepare()
        self.render(renderer)

    @timer
    def render(self, renderer: "AbstractRenderer"):
        renderer.start(
            original_ratio=self.final_size_px_f.ratio,
            size_chars=self.final_size_chars,
            background=self.color_converter.closest(self.config.background) if self.config.background else None,
        )
        for character in self.generate():
            renderer.render_character(character)
        renderer.finish()

    def zoom_and_render(self, renderer: "AbstractRenderer", factor: float, center: "PointF | None" = None):
        self.zoom(factor, center)
        self.render(renderer)

    @timer
    def zoom(self, factor: float, center: "PointF | None" = None):
        """
        Optimally, this method is run on an already prepared (and hopefully
        rendered, otherwise there will be some redundant work) image, so we
        know if the (fullsize) image should have transparent areas cropped
        away (self.visible_cropbox).

        1. Apply previously calculated cropbox, if it exists.
        2. Calculate a viewport exactly fitting the current image size, then
           shrink it by the inverse of `factor` (since `factor` indicates how
           the image should be scaled compared to one fitting into the
           viewport).
        3. Expand cropbox to fit the virtual viewport from #2.
        4. Crop a copy of the original image. We now have an image containing
           only the part that will be displayed, but probably in the wrong
           size; we do it in this order because cropping is cheaper than
           resizing for large images.
        5. Calculate matrix visibility from config unless the whole image
           already was found to be opaque (micro-optimization). This data will
           probably be destroyed by later operations, but we need it in order
           to know if the image is opaque.
        6. If image is opaque:
           6.1. Resize to 1px per output character
           6.2. Set image.pixel_ratio (see comment in image.py)
           6.3. Enhance
           6.4. Fill transparent and semi-transparent pixels with a mix of
              their original colour and background colour (see comments in
              this function)
        7. Otherwise:
           7.1. Resize to final size
           7.2. Enhance
           7.3. Update visibility data again, because image.resize() has
              probably destroyed it
        """
        self.image = self.original_image.copy()
        image_size = self.image.size.to_size_f()
        cropbox = SubRectF(image_size, image_size.to_rect_f())

        if self.visible_cropbox:  # 1
            cropbox = self.visible_cropbox.to_subrect_f().scale_container(image_size)
            image_size = cropbox.rect.size

        resized_viewport = self.config.viewport_size_px.fit_outside(image_size) * (1 / factor)  # 2
        cropbox = cropbox.crop_to_size(resized_viewport, center)  # 3
        self.image.crop(cropbox.to_subrect(round_for_ratio=True))  # 4

        if self.is_whole_image_opaque:  # 5
            self.image.is_opaque = True
        else:
            self.__update_visibility(self.image)

        if self.is_whole_image_opaque or self.image.is_opaque:
            self.image.resize(self.final_size_chars)  # 6.1
            self.image.pixel_ratio = 1 / self.config.char_ratio  # 6.2
            self.__enhance(self.image)  # 6.3
            self.image.fill_transparency(self.config.background)  # 6.4
        else:
            self.image.resize(self.final_size_px)  # 7.1
            self.__enhance(self.image)  # 7.2
            if self.image.is_matrix_stale:
                self.__update_visibility(self.image)  # 7.3

    def __enhance(self, image: ImagePlus):
        image.enhance(
            brightness=self.config.brightness,
            color_balance=self.config.color_balance,
            contrast=self.config.contrast,
            sharpness=self.config.sharpness,
            invert=self.config.invert,
        )

    @timer
    def __get_character(self, matrix: ImageArray, rect: "IndexedSizePartition") -> Character:
        section = matrix[rect.top : rect.bottom, rect.left : rect.right]
        section_area = section.shape[0] * section.shape[1]

        if self.image.is_opaque:
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
            column=rect.column,
            row=rect.row,
            color=(
                self.color_converter.get_section_color(section, self.config.color_inference) or
                self.config.default_color
            ),
        )

    @timer
    def __update_visibility(self, image: ImagePlus):
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
