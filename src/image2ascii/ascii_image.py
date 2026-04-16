from io import BytesIO, IOBase
from os import PathLike
from pathlib import Path
from typing import IO, TYPE_CHECKING, Any, Generator, Self, cast

import cairosvg
import numpy as np
from PIL import Image, ImageEnhance, ImageOps

from image2ascii.character import Character
from image2ascii.color import A, B, G, R, Vi, get_perceived_brightness
from image2ascii.geometry import PositionedBoxF, Size, SizeF, SubRect
from image2ascii.registry import Registry
from image2ascii.timing import timer
from image2ascii.types import ImageArray


if TYPE_CHECKING:
    from image2ascii.color_converters import AbstractColorConverter
    from image2ascii.config import Config
    from image2ascii.geometry import PointF, PositionedBoxPartition, ShapeSet
    from image2ascii.renderers import AbstractRenderer

    OptionalPoint = tuple[float, float] | PointF | None


class AsciiImage:
    config: "Config"
    image: Image.Image
    original_image: Image.Image
    color_converter: "AbstractColorConverter"
    shapeset: type["ShapeSet"]

    pixelmapped_image: Image.Image | None = None

    @property
    def image_size(self) -> Size:
        return Size.i(self.image)

    @property
    def original_image_size(self) -> Size:
        return Size.i(self.original_image)

    @property
    def final_size_chars(self) -> SizeF:
        """Final number of columns & rows of the ASCII output"""
        return self.config.viewport_size.fit_ratio(self.image_size.ratio / self.config.char_ratio)

    @property
    def final_size_px(self) -> SizeF:
        """
        Final size the image will have before being converted to ASCII:
        - width = number of output columns * quality
        - height = number of output rows * quality / character w/h ratio
        """
        return self.final_size_chars * self.config.quality / SizeF(1, self.config.char_ratio)

    @timer
    def __init__(
        self,
        image: Image.Image,
        config: "Config",
        color_converter: "AbstractColorConverter | None" = None,
        shapeset: "type[ShapeSet] | None" = None,
    ):
        self.config = config
        self.color_converter = color_converter or config.color_converter()
        self.shapeset = shapeset or config.shapeset
        self.image = self.original_image = image
        self.plugins = Registry(config)

    @timer
    def create_image_matrix(self, image: Image.Image, is_final: bool = False) -> ImageArray:
        """
        Make sure any relevant enhancements (especially inversion) are done on
        the image before this method is run.

        Returns: 3-d array with shape = (image height, image width, 5), where
            the last axis contains the following values for each pixel:
            R(ed), G(reen), B(lue), A(lpha), Vi(sibility)
        """
        print(f"create_image_matrix: {image.width, image.height}")
        # 3-axis matrix: 5 colour parameters (R, G, B, A, Vi) for each pixel.
        # Init them with ones so the transparency checks can AND them away for
        # the Vi values later.
        matrix = cast(ImageArray, np.ones((image.height, image.width, 5), dtype=np.uint8))

        # Fill first 4 values with R, G, B, A
        matrix[:, :, : A + 1] = np.asarray(image)

        if is_final:
            matrix = self.plugins.pre_create_matrix(image, matrix)

        # Now to find the Vi (visibility) values with up to 3 methods.
        # We AND together the Vi values with new ones & zeros, because we want
        # each method to potentially add _more_ transparency, not remove any.

        # First check if we should determine visibility by background colour
        # (dis-)similarity:
        if self.config.background and self.config.transparency.use_bgdistance(bool(self.config.background)):
            colors = matrix.reshape((matrix.shape[0] * matrix.shape[1], 5)).astype(np.int64)
            distances = self.config.background.get_distances(colors).reshape((matrix.shape[0], matrix.shape[1]))
            matrix[:, :, Vi] &= distances >= self.config.transparency.bg_distance

        # Maybe we should let "perceived brightness" do its thing:
        if self.config.transparency.use_brightness(bool(self.config.background)):
            perceived_brightness = get_perceived_brightness(matrix[:, :, R], matrix[:, :, G], matrix[:, :, B])
            matrix[:, :, Vi] &= perceived_brightness >= self.config.transparency.brightness

        # Check if there are literally transparent pixels:
        if self.config.transparency.use_alpha():
            matrix[:, :, Vi] &= matrix[:, :, A] >= self.config.transparency.alpha

        if is_final:
            matrix = self.plugins.post_create_matrix(image, matrix)

        return matrix

    @timer
    def crop_to_visible(self) -> Image.Image:
        if self.config.crop:
            matrix = self.create_image_matrix(self.image)
            cropbox = SubRect.from_visible(matrix)

            if cropbox.size != self.image_size:
                return self.image.crop(cropbox.tuple)

        return self.image

    @timer
    def crop_zoomed_area(self, zoom: float, center: "OptionalPoint" = None) -> Image.Image:
        center = center or (0.5, 0.5)
        box = (
            PositionedBoxF(self.final_size_px, self.config.viewport_size_px)
            .zoom(zoom)
            .place_relatively(center)
            .scale(self.original_image_size)
            .scale(self.image_size)
        )
        cropbox = box.visible_box.to_subrect(round_for_ratio=True)
        return self.image.crop(cropbox.tuple)
        # return self.original_image.crop(cropbox.tuple)

    @timer
    def enhance(self) -> Image.Image:
        image = self.plugins.pre_enhance(self.image)

        if self.config.brightness != 1.0:
            image = ImageEnhance.Brightness(image).enhance(self.config.brightness)
        if self.config.contrast != 1.0:
            image = ImageEnhance.Contrast(image).enhance(self.config.contrast)
        if self.config.sharpness != 1.0:
            image = ImageEnhance.Sharpness(image).enhance(self.config.sharpness)
        if self.config.color_balance != 1.0:
            image = ImageEnhance.Color(image).enhance(self.config.color_balance)
        if self.config.invert:
            # For some reason, PIL.ImageOps.invert() does not support RGBA.
            # This implementation leaves the alpha channel as it is.
            if image.mode == "RGBA":
                lut = list(range(0xFF, -1, -1)) * 3 + list(range(0xFF + 1))
                image = image.point(lut)
            else:
                image = ImageOps.invert(image)

        return self.plugins.post_enhance(image)

    @timer
    def ensure_max_original_size(self) -> Image.Image:
        if self.config.max_original_size:
            max_size = Size(self.config.max_original_size, self.config.max_original_size)

            if max_size < self.image_size:
                image_size = self.image_size.fit_inside(max_size, grow=False).to_size(round_for_ratio=True)
                if image_size.width <= 0 or image_size.height <= 0:
                    raise ValueError(
                        f"max_original_size={self.config.max_original_size} requires a resize to {image_size.width}x"
                        f"{image_size.height}, which is not possible.",
                    )
                return self.resize_image(image_size.tuple)

        return self.image

    @timer
    def generate(self) -> Generator[Character, Any, None]:
        if self.pixelmapped_image:
            image = self.pixelmapped_image
        else:
            image = self.image

        # 7. Create matrix
        matrix = self.create_image_matrix(image, is_final=True)

        # 8. Partition & yield chars
        if self.pixelmapped_image:
            columns, rows = image.width, image.height
        else:
            columns, rows = self.final_size_chars.to_size().tuple

        for box in Size(image.width, image.height).partition(columns, rows):
            yield self.__get_character(matrix, box)

    @timer
    def has_invisibility(self) -> bool:
        if self.config.transparency.use_nothing(bool(self.config.background)):
            return False

        matrix = self.create_image_matrix(self.image)
        return not np.all(matrix[:, :, Vi])

    @timer
    def prepare(self, zoom: float = 1.0, center: "OptionalPoint" = None):
        """
        1. Resize to final_size_px
        2. Convert to RGBA
        3. Enhance
        4. Crop away transparent; keep cropbox

        Zoom (using same object, with previously displayed image):
        1. Calculate visible box from cropbox above + scale + x, y
        2. From original image, crop to visible box
        3. Resize to final_size_px
        4. Enhance
        """
        self.image = self.original_image
        self.pixelmapped_image = None

        # 1. Shrink img if > config.max_original_size
        self.image = self.original_image = self.ensure_max_original_size()

        # 2. Convert to correct mode if necessary
        if self.image.mode != "RGBA":
            self.image = self.image.convert("RGBA")

        # 5. Crop zoomed area if zoom
        if zoom != 1.0:
            self.image = self.crop_zoomed_area(zoom, center)

        # final_size = self.final_size_px.to_size(round_for_ratio=True)
        # if final_size < self.image_size:
        #     self.image = self.resize_image(final_size.tuple)

        # 3. Enhance
        self.image = self.enhance()

        # 4. Crop away invisible "borders"
        self.image = self.crop_to_visible()

        # 6a. If not has_invisibility: resize img to size_chars.width x (size_chars.height * config.char_ratio)
        if not self.has_invisibility():
            self.pixelmapped_image = self.resize_image(self.final_size_chars.to_size(round_for_ratio=True).tuple)
        # 6b. Elif image size != config.viewport_size * config.quality: resize img to that
        else:
            final_size = self.final_size_px.to_size(round_for_ratio=True)
            if final_size != self.image_size:
                self.image = self.resize_image(final_size.tuple)

    def prepare_and_render(self, renderer: "AbstractRenderer", zoom: float = 1.0, center: "OptionalPoint" = None):
        self.prepare(zoom, center)
        self.render(renderer)

    @timer
    def render(self, renderer: "AbstractRenderer"):
        renderer.start(
            original_ratio=self.final_size_px.ratio,
            size_chars=self.final_size_chars,
            background=self.color_converter.closest(self.config.background) if self.config.background else None,
        )
        for character in self.generate():
            renderer.render_character(character)
        renderer.finish()

    @timer
    def resize_image(self, size: tuple[int, int]) -> Image.Image:
        return self.image.resize(size, resample=self.config.resample)

    @timer
    def __get_character(self, matrix: ImageArray, box: "PositionedBoxPartition") -> Character:
        section = matrix[box.top : box.bottom, box.left : box.right]
        section_area = section.shape[0] * section.shape[1]

        if self.pixelmapped_image:
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
    def load(cls, file: str | bytes | PathLike | Path | IO[bytes], config: "Config | None" = None) -> Self:
        from image2ascii.config import Config

        config = config or Config()
        if isinstance(file, Path):
            file = str(file)

        with Image.open(file) as original:
            original.load()
            ImageOps.exif_transpose(original, in_place=True)

        return cls(original, config)

    @classmethod
    def load_svg(cls, file: str | bytes | PathLike | Path | IO[bytes], config: "Config | None" = None) -> Self:
        from image2ascii.config import Config

        config = config or Config()
        output = BytesIO()
        kwargs = {
            "output_width": config.viewport_size_px.width,
            "output_height": config.viewport_size_px.height,
            "write_to": output,
        }

        if isinstance(file, bytes):
            kwargs["bytestring"] = file
        elif isinstance(file, IOBase):
            kwargs["file_obj"] = file
        else:
            kwargs["url"] = str(file)

        cairosvg.svg2png(**kwargs)

        return cls.load(output, config)
