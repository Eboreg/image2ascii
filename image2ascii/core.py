#!/usr/bin/env python3

from statistics import mean
from typing import Optional

from PIL import Image, ImageEnhance, ImageOps

from image2ascii import (
    DEFAULT_ASCII_RATIO, DEFAULT_ASCII_WIDTH, DEFAULT_MIN_LIKENESS, DEFAULT_QUALITY, EMPTY_CHARACTER,
)
from image2ascii.color import RGB, ColorConverter
from image2ascii.geometry import Matrix, Shape
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
    boolmatrix: Matrix[bool]
    color_converter: ColorConverter
    colormatrix: Matrix[tuple]
    image: Image.Image
    prepared: bool
    source_width: int
    source_height: int
    section_width: int
    section_height: int

    def __init__(
        self,
        filename: str,
        ascii_width: int = DEFAULT_ASCII_WIDTH,
        quality: int = DEFAULT_QUALITY,
        ascii_ratio: float = DEFAULT_ASCII_RATIO,
        invert: bool = False,
    ):
        self.invert = invert
        self.ascii_width = ascii_width
        self.quality = quality
        self.ascii_ratio = ascii_ratio
        self.color_converter = ColorConverter()

        self.load(filename)

    def set_color_converter(self, value: ColorConverter):
        if value.__class__ != self.color_converter.__class__:
            self.color_converter = value
            self.prepared = False
        return self

    def set_quality(self, value: int):
        if value != self.quality:
            self.quality = value
            self.prepared = False
        return self

    def set_ascii_width(self, value: int):
        if value != self.ascii_width:
            self.ascii_width = value
            self.prepared = False
        return self

    def set_ascii_ratio(self, value: float):
        if value != self.ascii_ratio:
            self.ascii_ratio = value
            self.prepared = False
        return self

    def set_invert(self, value: bool):
        if value != self.invert:
            self.invert = value
            self.prepared = False
        return self

    def enhance(self, contrast: float = 1.0, brightness: float = 1.0, color_balance: float = 1.0):
        self.image = enhance_image(self.image, contrast, brightness, color_balance)
        self.prepared = False
        return self

    def invert_colors(self):
        self.image = invert_image(self.image)
        self.prepared = False
        return self

    def crop(self):
        if not hasattr(self, "boolmatrix"):
            self.boolmatrix = self.get_boolmatrix(self.image, self.invert)
        box = self.boolmatrix.crop()
        self.image = self.image.crop(box)
        self.prepared = False
        return self

    def prepare(self):
        """
        Must always be run after any changed settings and before render().
        """
        # Downsize image to width (ascii_width * quality)
        max_width = self.ascii_width * self.quality
        if self.image.width > max_width:
            self.image = self.image.resize((max_width, int((max_width / self.image.width) * self.image.height)))
            self.boolmatrix = self.get_boolmatrix(self.image, self.invert)
        elif not hasattr(self, "boolmatrix"):
            self.boolmatrix = self.get_boolmatrix(self.image, self.invert)

        self.source_width, self.source_height = self.image.width, self.image.height

        # Save colours
        default = (0,) * len(self.image.getbands())
        self.colormatrix = Matrix(self.image.width, self.image.height, default, list(self.image.getdata()))

        # Each character will represent an image section this large
        self.section_width = int(self.source_width / self.ascii_width) or 1
        self.section_height = int(self.section_width * self.ascii_ratio) or 1

        self.init_shapes(self.section_width, self.section_height)

        self.prepared = True

        return self

    def load(self, filename: str):
        with Image.open(filename) as image:
            image.load()
        self.prepared = False
        self.image = image
        return self

    def get_boolmatrix(self, image: Image.Image, invert=False) -> Matrix[bool]:
        mono = image.convert("1", dither=Image.NONE)
        if invert:
            monodata = [v == 0 for v in list(mono.getdata())]
        else:
            monodata = [v != 0 for v in list(mono.getdata())]
        if image.mode == "RGBA":
            # Transparent pixels = False
            for idx, pixel in enumerate(list(image.getdata())):
                if pixel[-1] == 0:
                    monodata[idx] = False
        return Matrix(mono.width, mono.height, False, monodata)

    def init_shapes(self, width: int, height: int):
        """
        Ordering is relevant for performance; start with completely filled and
        completely empty shapes, then try and order them by size of filled
        area (smallest first).
        """
        self.shapes = [
            Shape(char=char, points=points, width=width, height=height)
            for char, points in [
                (EMPTY_CHARACTER, ((0, 0),)),
                ("$", ((0, 0), (1, 0), (1, 1), (0, 1))),
                (".", ((0, 0.8), (1, 0.8), (1, 1), (0, 1))),
                ("°", ((0, 0), (1, 0), (1, 0.3), (0, 0.3))),
                ("o", ((0, 0.5), (1, 0.5), (1, 1), (0, 1))),
                ("*", ((0, 0), (1, 0), (1, 0.5), (0, 0.5))),
                ("b", ((0, 0), (1, 1), (0, 1))),
                ("d", ((1, 0), (1, 1), (0, 1))),
                ("P", ((0, 0), (1, 0), (0, 1))),
                ("?", ((0, 0), (1, 0), (1, 1))),
            ]
        ]

    def render(
        self,
        formatter: Optional[BaseFormatter] = None,
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
        assert self.prepared, "You need to run prepare() before render()"

        if formatter is None:
            if color:
                formatter = ANSIFormatter()
            else:
                formatter = ASCIIFormatter()

        output = Output(formatter)
        last_color = None

        for start_y in range(0, self.source_height, self.section_height):
            for start_x in range(0, self.source_width, self.section_width):
                section = Matrix(self.section_width, self.section_height, False)
                section_colors = []
                # Loop over all pixels in section
                for y in range(self.section_height):
                    # The last row of sections will most likely extend a bit
                    # further down than the image height
                    if start_y + y == self.boolmatrix.height:
                        break
                    for x in range(self.section_width):
                        # Perhaps there could be overflow horizontally as well
                        if start_x + x == self.boolmatrix.width:
                            break
                        pixel_value = self.boolmatrix[start_y + y][start_x + x]
                        section[y][x] = pixel_value
                        if pixel_value and color:
                            section_colors.append(self.colormatrix[start_y + y][start_x + x])
                if section:
                    if color and section_colors:
                        color_value = [
                            mean([c[idx] for c in section_colors])
                            for idx in range(3)
                        ]
                        new_color = self.color_converter.from_rgb(RGB(*color_value))
                        if new_color != last_color:
                            output.add_color(new_color)
                            last_color = new_color
                    output.add_text(self.get_char(section, min_likeness))
            output.add_br()
        return output.render()

    def get_char(self, section_matrix: Matrix, min_likeness: float) -> str:
        chars = []  # list of (char, likeness) tuples
        for shape in self.shapes:
            likeness = shape.likeness(section_matrix)
            if likeness > min_likeness:
                return shape.char
            chars.append((shape.char, likeness))
        return max(chars, key=lambda c: c[1])[0]
