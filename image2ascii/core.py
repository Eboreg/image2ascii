#!/usr/bin/env python3

from statistics import mean
from typing import List, Optional, Tuple, Type

from PIL import Image, ImageEnhance, ImageOps

from image2ascii import (
    DEFAULT_ASCII_RATIO, DEFAULT_ASCII_WIDTH, DEFAULT_MIN_LIKENESS, DEFAULT_QUALITY, EMPTY_CHARACTER, FILLED_CHARACTER,
)
from image2ascii.color import RGB, ColorConverter, ColorConverterInvertBW
from image2ascii.geometry import BaseShape, CropBox, EmptyShape, FilledShape, Matrix, PolygonShape
from image2ascii.output import ANSIFormatter, BaseFormatter, Output


def enhance_image(
    image: Image.Image,
    contrast: float = 1.0,
    brightness: float = 1.0,
    color_balance: float = 1.0,
):
    if contrast != 1.0:
        image = ImageEnhance.Contrast(image).enhance(contrast)
    if brightness != 1.0:
        image = ImageEnhance.Brightness(image).enhance(brightness)
    if color_balance != 1.0:
        image = ImageEnhance.Color(image).enhance(color_balance)
    return image


def invert_image(image: Image.Image) -> Image.Image:
    """
    For some reason, PIL.ImageOps.invert() does not support RGBA.
    This implementation leaves the alpha channel as it is.
    """
    if image.mode == "RGBA":
        lut = [i for i in range(0xff, -1, -1)] * 3 + [i for i in range(0xff + 1)]
        return image.point(lut)
    return ImageOps.invert(image)


class Image2ASCII:
    _ascii_ratio: float = DEFAULT_ASCII_RATIO
    _ascii_width: int = DEFAULT_ASCII_WIDTH
    _brightness: float = 1.0
    _color: bool = False
    _color_balance: float = 1.0
    _color_converter_class: Type[ColorConverter] = ColorConverter
    _contrast: float = 1.0
    _crop: bool = False
    _fill_all: bool = False
    _invert: bool = False
    _invert_colors: bool = False
    _min_likeness: float = DEFAULT_MIN_LIKENESS
    _quality: int = DEFAULT_QUALITY

    formatter_class: Type[BaseFormatter] = ANSIFormatter
    image: Optional[Image.Image] = None
    output: Optional[Output] = None

    shapes: List[BaseShape]

    """
    PROPERTIES
    """
    @property
    def ascii_ratio(self) -> float:
        return self._ascii_ratio

    @ascii_ratio.setter
    def ascii_ratio(self, value: float):
        if value != self._ascii_ratio:
            self._ascii_ratio = value
            self.reset()

    @property
    def ascii_width(self) -> int:
        return self._ascii_width

    @ascii_width.setter
    def ascii_width(self, value: int):
        if value != self._ascii_width:
            self._ascii_width = value
            self.reset()

    @property
    def brightness(self) -> float:
        return self._brightness

    @brightness.setter
    def brightness(self, value: float):
        if value != self._brightness:
            self._brightness = value
            self.reset()

    @property
    def color(self) -> bool:
        return self._color

    @color.setter
    def color(self, value: bool):
        if value != self._color:
            self._color = value
            self.reset()

    @property
    def color_balance(self) -> float:
        return self._color_balance

    @color_balance.setter
    def color_balance(self, value: float):
        if value != self._color_balance:
            self._color_balance = value
            self.reset()

    @property
    def color_converter_class(self) -> Type[ColorConverter]:
        return self._color_converter_class

    @color_converter_class.setter
    def color_converter_class(self, value: Type[ColorConverter]):
        if value != self._color_converter_class:
            self._color_converter_class = value
            self.reset()

    @property
    def contrast(self) -> float:
        return self._contrast

    @contrast.setter
    def contrast(self, value: float):
        if value != self._contrast:
            self._contrast = value
            self.reset()

    @property
    def crop(self) -> bool:
        return self._crop

    @crop.setter
    def crop(self, value: bool):
        if value != self._crop:
            self._crop = value
            self.reset()

    @property
    def fill_all(self) -> bool:
        return self._fill_all

    @fill_all.setter
    def fill_all(self, value: bool):
        if value != self._fill_all:
            self._fill_all = value
            self.reset()

    @property
    def invert(self) -> bool:
        return self._invert

    @invert.setter
    def invert(self, value: bool):
        if value != self._invert:
            self._invert = value
            self.reset()

    @property
    def invert_colors(self) -> bool:
        return self._invert_colors

    @invert_colors.setter
    def invert_colors(self, value: bool):
        if value != self._invert_colors:
            self._invert_colors = value
            self.reset()

    @property
    def min_likeness(self) -> float:
        return self._min_likeness

    @min_likeness.setter
    def min_likeness(self, value: float):
        if value != self._min_likeness:
            self._min_likeness = value
            self.reset()

    @property
    def quality(self) -> int:
        return self._quality

    @quality.setter
    def quality(self, value: int):
        if value != self._quality:
            self._quality = value
            self.reset()

    """
    CONVENIENCE SETTINGS METHODS
    """
    def color_settings(
        self,
        color: Optional[bool] = None,
        invert: Optional[bool] = None,
        invert_colors: Optional[bool] = None,
        fill_all: Optional[bool] = None,
        swap_bw: Optional[bool] = None
    ):
        if color is not None:
            self.color = color
        if invert is not None:
            self.invert = invert
        if invert_colors is not None:
            self.invert_colors = invert_colors
        if fill_all is not None:
            self.fill_all = fill_all
        if swap_bw is not None:
            self.color_converter_class = ColorConverterInvertBW if swap_bw else ColorConverter

    def enhancement_settings(
        self,
        contrast: Optional[float] = None,
        brightness: Optional[float] = None,
        color_balance: Optional[float] = None
    ):
        if contrast is not None:
            self.contrast = contrast
        if brightness is not None:
            self.brightness = brightness
        if color_balance is not None:
            self.color_balance = color_balance

    def quality_settings(self, quality: Optional[int] = None, min_likeness: Optional[float] = None):
        if quality is not None:
            self.quality = quality
        if min_likeness is not None:
            self.min_likeness = min_likeness

    def size_settings(
        self,
        ascii_width: Optional[int] = None,
        ascii_ratio: Optional[float] = None,
        crop: Optional[bool] = None
    ):
        if ascii_width is not None:
            self.ascii_width = ascii_width
        if ascii_ratio is not None:
            self.ascii_ratio = ascii_ratio
        if crop is not None:
            self.crop = crop

    """
    THE REST OF THE JAZZ
    """
    def do_crop(self, image: Image.Image) -> Image.Image:
        if self.crop:
            boolmatrix = self.get_boolmatrix(image)
            cropbox = boolmatrix.get_crop_box()
            image = image.crop(cropbox)
        return image

    def do_enhance(self, image: Image.Image) -> Image.Image:
        return enhance_image(image, self.contrast, self.brightness, self.color_balance)

    def reset(self):
        self.output = None

    def do_resize(self, image: Image.Image) -> Tuple[int, int, Image.Image]:
        """
        Resize image to a multiple of the sizes of the sections it will be
        divided into, with a width not exceeding self.ascii_width *
        self.quality.

        Returns: section_width, section_height, resized image
        """
        end_width = self.ascii_width * self.quality

        if image.width < end_width:
            end_width = image.width - (image.width % self.ascii_width)

        if image.width != end_width:
            image = image.resize((end_width, round((end_width / image.width) * image.height)))

        # Each character will represent an image section this large
        section_width = int(image.width / self.ascii_width) or 1
        section_height = int(section_width * self.ascii_ratio) or 1

        # If image height is not an exact multiple of section heights, expand
        # it vertically so it becomes so.
        if image.height % section_height:
            expand_height = section_height - (image.height % section_height)
            box = CropBox(
                left=0,
                upper=(int(expand_height / 2) + expand_height % 2) * -1,
                right=image.width,
                lower=image.height + int(expand_height / 2)
            )
            image = image.crop(box)

        return section_width, section_height, image

    def prepare_image(self) -> Tuple[int, int, Image.Image]:
        """
        Returns: section_width, section_height, prepared image
        """
        if self.image is None:
            raise ValueError("You need to run .load(file)")
        image = self.do_crop(self.image)
        section_width, section_height, image = self.do_resize(image)
        image = self.do_enhance(image)
        self.init_shapes(section_width, section_height)
        return section_width, section_height, image

    def get_colormatrix(self, image: Image.Image) -> Matrix[tuple]:
        default = (0,) * len(image.getbands())
        return Matrix(image.width, image.height, default, list(image.getdata()))

    def load(self, file):
        with Image.open(file) as image:
            image.load()
        self.reset()
        # Needs to be RGBA in order for any vertical lines added by
        # self.resize() to become transparent
        if image.mode != "RGBA":
            image = image.convert("RGBA")
        # Downsize original if it's ridiculously large
        if image.width > 2000 or image.height > 2000:
            factor = 2000 / max(image.width, image.height)
            image = image.resize((round(image.width * factor), round(image.height * factor)))
        self.image = image

    def get_boolmatrix(self, image: Image.Image) -> Matrix[bool]:
        """
        If self.fill_all: Only transparent pixels (more precisely: those with
            alpha < 0x80) will be considered filled. Otherwise,
            filled/unfilled status will depend on whatever a conversion to
            monochrome spits out.
        If self.invert: Reverses the filled/unfilled status for all pixels.
        """
        if self.fill_all:
            if image.mode == "RGBA":
                monodata = [v[-1] >= 0x80 for v in list(image.getdata())]
            else:
                monodata = [True] * image.width * image.height
        else:
            mono = image.convert("1", dither=Image.NONE)
            monodata = [v != 0 for v in list(mono.getdata())]
            if image.mode == "RGBA":
                # Transparent pixels = False
                for idx, pixel in enumerate(list(image.getdata())):
                    if pixel[-1] < 0x80:
                        monodata[idx] = False
        if self.invert:
            monodata = [not v for v in monodata]

        return Matrix(image.width, image.height, False, monodata)

    def init_shapes(self, section_width: int, section_height: int):
        """
        Ordering is relevant for performance; start with completely filled and
        completely empty shapes, then try and order them by size of filled
        area (smallest first).
        """
        self.shapes = [
            EmptyShape(EMPTY_CHARACTER),
            FilledShape(FILLED_CHARACTER),
        ]
        self.shapes.extend([
            PolygonShape(char=char, points=points, width=section_width, height=section_height)
            for char, points in [
                ("o", ((0, 0.5), (1, 0.5), (1, 1), (0, 1))),
                ("*", ((0, 0), (1, 0), (1, 0.5), (0, 0.5))),
                (".", ((0, 0.7), (1, 0.7), (1, 1), (0, 1))),
                ("°", ((0, 0), (1, 0), (1, 0.3), (0, 0.3))),
                ("b", ((0, 0), (1, 1), (0, 1))),
                ("d", ((1, 0), (1, 1), (0, 1))),
                ("P", ((0, 0), (1, 0), (0, 1))),
                ("?", ((0, 0), (1, 0), (1, 1))),
            ]
        ])

    def render(self):
        """
        Divides image into (self.section_width, self.section_height) sized
        sections, or more specifically: extracts boolean matrices for each of
        those sections. Then gets the most suitable ASCII character for
        each section and concatenates them together. Then renders the result
        in the selected format.
        """
        if self.output is None:
            section_width, section_height, image = self.prepare_image()
            self.output = Output()
            boolmatrix = self.get_boolmatrix(image)

            if self.color:
                last_color = None
                colormatrix = self.get_colormatrix(image)
                color_converter = self.color_converter_class()

            for start_y in range(0, image.height, section_height):
                for start_x in range(0, image.width, section_width):
                    section = Matrix(section_width, section_height, False)
                    section_colors = []
                    # Loop over all pixels in section
                    for y in range(section_height):
                        for x in range(section_width):
                            pixel_value = boolmatrix[start_y + y][start_x + x]
                            section[y][x] = pixel_value
                            if pixel_value and self.color:
                                section_colors.append(colormatrix[start_y + y][start_x + x])
                    if section:
                        if self.color and section_colors:
                            color_value = [
                                mean([c[idx] for c in section_colors])
                                for idx in range(3)
                            ]
                            new_color = color_converter.from_rgb(RGB(*color_value))
                            if new_color != last_color:
                                self.output.add_color(new_color)
                                last_color = new_color
                        self.output.add_text(self.get_char(section))
                self.output.add_br()
        return self.formatter_class(self.output).render()

    def get_char(self, section_matrix: Matrix) -> str:
        chars = []  # list of (char, likeness) tuples

        for shape in self.shapes:
            likeness = shape.likeness(section_matrix)
            if likeness > self.min_likeness:
                return shape.char
            chars.append((shape.char, likeness))
        return max(chars, key=lambda c: c[1])[0]
