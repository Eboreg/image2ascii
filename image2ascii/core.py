#!/usr/bin/env python3

from statistics import mean
from typing import Optional, Type

from PIL import Image, ImageEnhance, ImageOps

from image2ascii import (
    DEFAULT_ASCII_RATIO, DEFAULT_ASCII_WIDTH, DEFAULT_MIN_LIKENESS, DEFAULT_QUALITY, EMPTY_CHARACTER, FILLED_CHARACTER,
)
from image2ascii.color import RGB, ColorConverter
from image2ascii.geometry import CropBox, Matrix, Shape
from image2ascii.output import ANSIFormatter, ASCIIFormatter, BaseFormatter, Output


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
    color: bool
    color_converter: ColorConverter
    cropbox: Optional[CropBox]
    fill_all: bool
    formatter_class: Type[BaseFormatter]
    image: Image.Image
    min_likeness: float
    output: Optional[Output]
    prepared: bool
    source_width: int
    source_height: int
    section_width: int
    section_height: int

    def __init__(
        self,
        file,
        ascii_width: int = DEFAULT_ASCII_WIDTH,
        quality: int = DEFAULT_QUALITY,
        ascii_ratio: float = DEFAULT_ASCII_RATIO,
        invert: bool = False,
        fill_all: bool = False,
    ):
        self.invert = invert
        self.ascii_width = ascii_width
        self.quality = quality
        self.ascii_ratio = ascii_ratio
        self.color_converter = ColorConverter()
        self.fill_all = fill_all
        self.formatter_class = ASCIIFormatter
        self.color = False
        self.min_likeness = DEFAULT_MIN_LIKENESS
        self.output = None
        self.cropbox = None
        self.prepared = False

        self.load(file)

    def set_color_converter(self, value: ColorConverter):
        if value.__class__ != self.color_converter.__class__:
            self.color_converter = value
            self.reset()
        return self

    def set_quality(self, value: int):
        if value != self.quality:
            self.quality = value
            self.reset()
        return self

    def set_ascii_width(self, value: int):
        if value != self.ascii_width:
            self.ascii_width = value
            self.reset()
        return self

    def set_ascii_ratio(self, value: float):
        if value != self.ascii_ratio:
            self.ascii_ratio = value
            self.reset()
        return self

    def set_invert(self, value: bool):
        if value != self.invert:
            self.invert = value
            self.reset()
        return self

    def set_fill_all(self, value: bool):
        if value != self.fill_all:
            self.fill_all = value
            self.reset()
        return self

    def enhance(self, contrast: float = 1.0, brightness: float = 1.0, color_balance: float = 1.0):
        self.image = enhance_image(self.image, contrast, brightness, color_balance)
        self.reset()
        return self

    def invert_colors(self):
        self.image = invert_image(self.image)
        self.reset()
        return self

    def crop(self):
        boolmatrix = self.get_boolmatrix()

        self.cropbox = boolmatrix.get_crop_box()
        self.image = self.image.crop(self.cropbox)

        self.reset()

        return self

    def reset(self):
        self.output = None
        self.prepared = False

    def resize(self):
        """
        Resize image to a multiple of the sizes of the sections it will be
        divided into, with a width not exceeding self.ascii_width *
        self.quality.
        """
        end_width = self.ascii_width * self.quality

        if self.image.width < end_width:
            end_width = self.image.width - (self.image.width % self.ascii_width)

        if self.image.width != end_width:
            self.image = self.image.resize((end_width, round((end_width / self.image.width) * self.image.height)))
            self.reset()

        # Each character will represent an image section this large
        self.section_width = int(self.image.width / self.ascii_width) or 1
        self.section_height = int(self.section_width * self.ascii_ratio) or 1

        # If image height is not an exact multiple of section heights, expand
        # it vertically so it becomes so.
        if self.image.height % self.section_height:
            expand_height = self.section_height - (self.image.height % self.section_height)
            box = CropBox(
                left=0,
                upper=(int(expand_height / 2) + expand_height % 2) * -1,
                right=self.image.width,
                lower=self.image.height + int(expand_height / 2)
            )
            self.image = self.image.crop(box)
            self.reset()

        self.source_width, self.source_height = self.image.width, self.image.height

    def prepare(self):
        if not self.prepared:
            self.resize()
            self.init_shapes()
        self.prepared = True

    def get_colormatrix(self) -> Matrix[tuple]:
        default = (0,) * len(self.image.getbands())
        return Matrix(self.image.width, self.image.height, default, list(self.image.getdata()))

    def load(self, file):
        with Image.open(file) as image:
            image.load()
        self.reset()
        # Needs to be RGBA in order for any vertical lines added by
        # self.resize() to become transparent
        if image.mode != "RGBA":
            image = image.convert("RGBA")
        self.image = image
        return self

    def get_boolmatrix(self) -> Matrix[bool]:
        """
        If self.fill_all: Only transparent pixels (more precisely: those with
            alpha < 0x80) will be considered filled. Otherwise,
            filled/unfilled status will depend on whatever a conversion to
            monochrome spits out.
        If self.invert: Reverses the filled/unfilled status for all pixels.
        """
        if self.fill_all:
            if self.image.mode == "RGBA":
                monodata = [v[-1] >= 0x80 for v in list(self.image.getdata())]
            else:
                monodata = [True] * self.image.width * self.image.height
        else:
            mono = self.image.convert("1", dither=Image.NONE)
            monodata = [v != 0 for v in list(mono.getdata())]
            if self.image.mode == "RGBA":
                # Transparent pixels = False
                for idx, pixel in enumerate(list(self.image.getdata())):
                    if pixel[-1] < 0x80:
                        monodata[idx] = False
        if self.invert:
            monodata = [not v for v in monodata]

        return Matrix(self.image.width, self.image.height, False, monodata)

    def init_shapes(self):
        """
        Ordering is relevant for performance; start with completely filled and
        completely empty shapes, then try and order them by size of filled
        area (smallest first).
        """
        self.shapes = [
            Shape(char=char, points=points, width=self.section_width, height=self.section_height)
            for char, points in [
                (EMPTY_CHARACTER, ((0, 0),)),
                (FILLED_CHARACTER, ((0, 0), (1, 0), (1, 1), (0, 1))),
                ("o", ((0, 0.5), (1, 0.5), (1, 1), (0, 1))),
                ("*", ((0, 0), (1, 0), (1, 0.5), (0, 0.5))),
                (".", ((0, 0.7), (1, 0.7), (1, 1), (0, 1))),
                ("°", ((0, 0), (1, 0), (1, 0.3), (0, 0.3))),
                ("b", ((0, 0), (1, 1), (0, 1))),
                ("d", ((1, 0), (1, 1), (0, 1))),
                ("P", ((0, 0), (1, 0), (0, 1))),
                ("?", ((0, 0), (1, 0), (1, 1))),
            ]
        ]

    def render(
        self,
        formatter_class: Optional[Type[BaseFormatter]] = None,
        color=False,
        min_likeness: float = DEFAULT_MIN_LIKENESS
    ):
        """
        Divides image into (self.section_width, self.section_height) sized
        sections, or more specifically: extracts boolean matrices for each of
        those sections. Then gets the most suitable ASCII character for
        each section and concatenates them together. Then renders the result
        in the selected format.
        """
        self.prepare()

        boolmatrix = self.get_boolmatrix()

        if formatter_class is None:
            if color:
                formatter_class = ANSIFormatter
            else:
                formatter_class = ASCIIFormatter

        if formatter_class != self.formatter_class:
            self.output = None
            self.formatter_class = formatter_class

        if color != self.color:
            self.output = None
            self.color = color

        if min_likeness != self.min_likeness:
            self.output = None
            self.min_likeness = min_likeness

        if self.output is None:
            self.output = Output(formatter_class)

            if color:
                last_color = None
                colormatrix = self.get_colormatrix()

            for start_y in range(0, self.source_height, self.section_height):
                for start_x in range(0, self.source_width, self.section_width):
                    section = Matrix(self.section_width, self.section_height, False)
                    section_colors = []
                    # Loop over all pixels in section
                    for y in range(self.section_height):
                        for x in range(self.section_width):
                            pixel_value = boolmatrix[start_y + y][start_x + x]
                            section[y][x] = pixel_value
                            if pixel_value and color:
                                section_colors.append(colormatrix[start_y + y][start_x + x])
                    if section:
                        if color and section_colors:
                            color_value = [
                                mean([c[idx] for c in section_colors])
                                for idx in range(3)
                            ]
                            new_color = self.color_converter.from_rgb(RGB(*color_value))
                            if new_color != last_color:
                                self.output.add_color(new_color)
                                last_color = new_color
                        self.output.add_text(self.get_char(section, min_likeness))
                self.output.add_br()
        return self.output.render()

    def get_char(self, section_matrix: Matrix, min_likeness: float) -> str:
        chars = []  # list of (char, likeness) tuples
        for shape in self.shapes:
            likeness = shape.likeness(section_matrix)
            if likeness > min_likeness:
                return shape.char
            chars.append((shape.char, likeness))
        return max(chars, key=lambda c: c[1])[0]
