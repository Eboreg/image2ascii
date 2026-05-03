import re
from collections.abc import Iterator
from os import PathLike
from pathlib import Path
from typing import IO, TYPE_CHECKING, Literal, Self

import requests

from image2ascii.color import A
from image2ascii.geometry import BiColorShape, PointF, SizeF, SubRect
from image2ascii.image import ImagePlus
from image2ascii.output import (
    BackgroundEnd,
    BackgroundStart,
    Character,
    ColorEnd,
    ColorStart,
    Linebreak,
    OutputAtom,
    OutputEnd,
    OutputStart,
    RowEnd,
    RowStart,
)
from image2ascii.registry import Registry
from image2ascii.timing import timer
from image2ascii.types import ImageArray


if TYPE_CHECKING:
    from image2ascii.color import Color
    from image2ascii.config import Config
    from image2ascii.geometry import Shape, Size
    from image2ascii.renderers import AbstractRenderer


class Workhorse:
    """
    This class is prepared for use as a context manager (i.e. with `with`),
    although neither `__enter__` nor `__exit__` does anything at the moment.

    I tried running `__get_section_character_string` and `__get_section_color`
    in parallel by sending them to a common ThreadPoolExecutor (whose `shutdown`
    method was run in `__exit__`), but this turned out to add so much overhead,
    it made the whole thing _slower_ instead:
        * `__get_character`, 4500 runs, without threads: 0.043187 s
        * `__get_character`, 4500 runs, with threads: 0.17162 s

    is_whole_image_opaque
    ---------------------
    This is used for a micro-optimization: If the whole image was found to be
    opaque, we know that all possible parts of it also are, so zoom() doesn't
    even need to check that. See also comments in image.py.
    """

    config: "Config"
    image: ImagePlus
    is_whole_image_opaque: bool = False
    original_image: ImagePlus
    visible_cropbox: "SubRect | None" = None

    @property
    def final_size_chars(self) -> "Size":
        return self.final_size_chars_f.to_size(round_for_ratio=True)

    @property
    def final_size_chars_f(self) -> SizeF:
        """Final number of columns & rows of the ASCII output"""
        return self.config.viewport.size.to_size_f().fit_ratio(
            self.image.ratio / self.config.char_ratio / self.image.pixel_ratio
        )

    @property
    def final_size_px(self) -> "Size":
        return self.final_size_px_f.to_size(round_for_ratio=True)

    @property
    def final_size_px_f(self) -> SizeF:
        """
        Final size the image will have before being converted to ASCII:
        - width = number of output columns * quality
        - height = number of output rows * quality / character w/h ratio
        """
        return self.final_size_chars_f * self.config.quality / SizeF(1, self.config.char_ratio)

    @timer
    def __init__(self, image: ImagePlus, config: "Config"):
        self.config = config
        self.original_image = image
        self.image = image.copy()
        self.plugins = Registry()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        pass

    @timer
    def generate_output(self) -> Iterator[OutputAtom]:
        image_background = self.__get_background()
        matrix = self.image.get_matrix(regenerate_if_stale=True)
        current_column = current_row = 0
        current_background: "Color | None" = None
        current_color: "Color | None" = None

        if self.image.is_opaque:
            columns, rows = self.image.size.tuple
        else:
            columns, rows = self.final_size_chars.tuple

        yield OutputStart(background=image_background)
        yield RowStart(row=0, background=image_background)

        for rect in self.image.size.partition(columns, rows):
            current_column = rect.column
            section = matrix[rect.top : rect.bottom, rect.left : rect.right]
            shape = self.__get_section_shape(section)
            opacity = self.__get_section_opacity(section) if shape.supports_opacity else 1

            if rect.row != current_row:
                yield RowEnd(row=current_row, background=image_background)
                yield Linebreak(old_row=current_row, new_row=rect.row)
                current_row = rect.row
                yield RowStart(row=current_row, background=image_background)
                # Trigger a redraw of foreground colour for next character:
                if current_color:
                    yield ColorEnd(color=current_color, column=current_column, row=current_row)
                    current_color = None

            if isinstance(shape, BiColorShape):
                section_color, section_background = self.__get_section_bicolor(section, shape.filled_part)
            else:
                section_color = self.__get_section_color(section)
                section_background = image_background

            if section_background != current_background:
                if current_background:
                    yield BackgroundEnd(column=current_column, row=current_row, color=current_background)
                if section_background:
                    yield BackgroundStart(color=section_background, column=current_column, row=current_row)
                current_background = section_background

            if section_color != current_color:
                if current_color:
                    yield ColorEnd(column=current_column, row=current_row, color=current_color)
                if section_color:
                    yield ColorStart(color=section_color, column=current_column, row=current_row)
                current_color = section_color

            yield Character(
                shape=shape,
                column=current_column,
                row=current_row,
                opacity=opacity,
                color=current_color,
                background=current_background,
            )

        yield RowEnd(row=current_row, background=image_background)
        if current_color:
            yield ColorEnd(column=0, row=current_row + 1, color=current_color)
        if current_background:
            yield BackgroundEnd(column=0, row=current_row + 1, color=current_background)
        yield OutputEnd(background=image_background)

    @timer
    def get_center_constraints(self, zoom_factor: float):
        """
        Given a zoom factor, return the highest and lowest values the `center`
        argument to self.zoom() may have without "panning past" the image.
        """
        if self.visible_cropbox:
            image_size = self.visible_cropbox.rect.size.to_size_f()
        else:
            image_size = self.original_image.size.to_size_f()

        fitted_image_size = image_size.fit_inside(self.config.viewport_size_px)
        zoomed_image_size = fitted_image_size * zoom_factor
        viewport_image_ratio = self.config.viewport_size_px / zoomed_image_size
        min_center_x = min(viewport_image_ratio.width, 1) / 2
        min_center_y = min(viewport_image_ratio.height, 1) / 2

        return PointF(min_center_x, min_center_y), PointF(1 - min_center_x, 1 - min_center_y)

    @timer
    def get_pan_steps(self, zoom_factor: float, viewport_step: float = 0.5):
        """
        Given a zoom factor, return the increments to add to the `center`
        argument to self.zoom() in order to pan the image by `viewport_step`
        viewports.

        Yes, this is all getting terribly complicated to reason about, and I
        should probably simplify it somehow.
        """
        min_center = self.get_center_constraints(zoom_factor)[0]
        return PointF(min_center.x * 2 * viewport_step, min_center.y * 2 * viewport_step)

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
        self.image.resize(self.final_size_px, resample=self.config.resample)  # 1
        self.__enhance(self.image)  # 2
        self.__update_visibility(self.image)  # 3

        if self.config.crop:  # 4
            self.visible_cropbox = self.image.get_visible_cropbox(regenerate_matrix_if_stale=True)
            if self.visible_cropbox.is_cropped:
                self.image.crop(self.visible_cropbox)
        else:
            # Just so zoom() knows this has already been done, and doesn't do
            # any redundant work:
            self.visible_cropbox = SubRect.from_size(self.image.size)

        if self.image.is_opaque:
            self.is_whole_image_opaque = True
            self.image.resize(self.final_size_chars, resample=self.config.resample)  # 5.1
            self.image.pixel_ratio = 1 / self.config.char_ratio  # 5.2
            self.image.fill_transparency(self.__get_background())  # 5.3
        else:
            self.is_whole_image_opaque = False
            self.image.resize(self.final_size_px, resample=self.config.resample)  # 6.1
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
        )
        for atom in self.generate_output():
            renderer.render_atom(atom)

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
        cropbox = SubRect.from_size(self.image.size).to_subrect_f()

        if self.visible_cropbox:  # 1
            cropbox = self.visible_cropbox.to_subrect_f().scale_container(image_size)
            image_size = cropbox.rect.size
        elif self.config.crop:
            cropbox = self.image.get_visible_cropbox(regenerate_matrix_if_stale=True).to_subrect_f()

        resized_viewport = self.config.viewport_size_px.fit_outside(image_size) * (1 / factor)  # 2
        # `center` is the relative point in the image where the viewport will
        # be centered (top left=(0, 0), bottom right=(1, 1)). But we want to
        # limit this value so the viewport doesn't "pan past" the image.
        if center is not None:
            center = center.coerce_between(*self.get_center_constraints(factor))
        cropbox = cropbox.crop_to_size(resized_viewport, center)  # 3
        self.image.crop(cropbox.to_subrect(round_for_ratio=True))  # 4

        if self.is_whole_image_opaque:  # 5
            self.image.is_opaque = True
        else:
            self.__update_visibility(self.image)

        if self.is_whole_image_opaque or self.image.is_opaque:
            self.image.resize(self.final_size_chars, resample=self.config.resample)  # 6.1
            self.image.pixel_ratio = 1 / self.config.char_ratio  # 6.2
            self.__enhance(self.image)  # 6.3
            self.image.fill_transparency(self.__get_background())  # 6.4
        else:
            self.image.resize(self.final_size_px, resample=self.config.resample)  # 7.1
            self.__enhance(self.image)  # 7.2
            if self.image.is_matrix_stale:
                self.__update_visibility(self.image)  # 7.3

    @timer
    def __enhance(self, image: ImagePlus):
        self.plugins.pre_enhance(image)
        image.enhance(
            brightness=self.config.effect.brightness,
            color_balance=self.config.effect.color_balance,
            contrast=self.config.effect.contrast,
            sharpness=self.config.effect.sharpness,
            invert=self.config.effect.invert,
            mirror=self.config.effect.mirror,
            rotate=self.config.effect.rotate,
            resample=self.config.resample,
        )
        self.plugins.post_enhance(image)

    @timer
    def __get_background(self) -> "Color | None":
        return (
            self.config.color.converter.closest(self.config.color.background)
            if self.config.color.background
            else None
        )

    @timer
    def __get_section_bicolor(
        self,
        section: ImageArray,
        filled_part: Literal["top", "bottom"],
    ) -> tuple["Color | None", "Color | None"]:
        """Returns: (foreground, background)"""
        center = section.shape[0] // 2
        top = self.config.color.converter.get_section_color(section[:center], self.config.color.inference)
        bottom = self.config.color.converter.get_section_color(section[center:], self.config.color.inference)
        background = self.__get_background()

        if filled_part == "top":
            return top or background, bottom or background
        return top or background, bottom or background

    @timer
    def __get_section_color(self, section: ImageArray) -> "Color | None":
        return (
            self.config.color.converter.get_section_color(section, self.config.color.inference)
            or self.config.color.default
        )

    @timer
    def __get_section_opacity(self, section: ImageArray) -> float:
        """Scale: 0..1"""
        return section[:, :, A].mean() / 0xFF

    @timer
    def __get_section_shape(self, section: ImageArray) -> "Shape":
        if self.image.is_opaque:
            return self.config.shapeset.FILLED

        return self.config.shapeset.get_shape(section, self.config.min_likeness)

    @timer
    def __update_visibility(self, image: ImagePlus):
        background = self.__get_background()

        # First check if we should determine visibility by background colour
        # (dis-)similarity:
        if background and self.config.transparency.use_bgdistance(bool(background)):
            image.update_visibility_by_bgdistance(background, self.config.transparency.bg_distance)

        # Maybe we should let "perceived brightness" do its thing:
        if self.config.transparency.use_brightness(bool(background)):
            image.update_visibility_by_brightness(self.config.transparency.brightness)

        # Check if there are literally transparent pixels:
        if self.config.transparency.use_alpha():
            image.update_visibility_by_alpha(self.config.transparency.alpha)

    @classmethod
    @timer
    def load_file(cls, path: str | Path, config: "Config | None" = None) -> Self:
        if isinstance(path, Path):
            path = str(path)
        if re.match(r"^https?://", path):
            return cls.load_http(url=path, config=config)
        if path.lower().endswith(".svg"):
            return cls.load_svg(path, config)
        return cls.load_image(path, config)

    @classmethod
    @timer
    def load_image(cls, file: str | bytes | PathLike | Path | IO[bytes], config: "Config | None" = None) -> Self:
        from image2ascii.config import Config

        return cls(ImagePlus.load(file), config or Config())

    @classmethod
    @timer
    def load_svg(cls, file: str | bytes | PathLike | Path | IO[bytes], config: "Config | None" = None) -> Self:
        from image2ascii.config import Config

        config = config or Config()
        return cls(ImagePlus.load_svg(file, output_size=config.viewport_size_px), config)

    @classmethod
    @timer
    def load_http(cls, url: str, config: "Config | None" = None) -> Self:
        response = requests.get(url, allow_redirects=True, timeout=10)
        if response.headers.get("Content-Type") == "image/svg+xml":
            return cls.load_svg(file=response.content, config=config)
        else:
            return cls.load_image(file=response.content, config=config)
