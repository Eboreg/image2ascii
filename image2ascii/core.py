#!/usr/bin/env python3

from statistics import mean
from typing import SupportsFloat, Tuple

from PIL import Image, ImageEnhance, ImageOps

from image2ascii import (
    DEFAULT_ASCII_RATIO, DEFAULT_ASCII_WIDTH, DEFAULT_MIN_LIKENESS, DEFAULT_QUALITY, EMPTY_CHARACTER,
)
from image2ascii.color import ANSIColorConverter, ANSIColorConverterInvertBW, Color
from image2ascii.geometry import Matrix, Shape


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
    color_converter: ANSIColorConverter
    colormatrix: Matrix[tuple]
    min_likeness: float
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
        min_likeness: float = DEFAULT_MIN_LIKENESS,
        contrast: float = 1.0,
        brightness: float = 1.0,
        crop: bool = False,
        invert: bool = False,
        color: bool = False,
        invert_colors: bool = False,
        color_balance: float = 1.0,
        swap_bw: bool = False,
    ):
        self.min_likeness = min_likeness
        self.crop = crop
        self.color = color
        self.invert = invert
        self.invert_colors = invert_colors
        self.color_balance = color_balance
        self.swap_bw = swap_bw

        if self.swap_bw:
            self.color_converter = ANSIColorConverterInvertBW()
        else:
            self.color_converter = ANSIColorConverter()

        with Image.open(filename) as image:
            # Do enhancements
            image = enhance_image(image, contrast, brightness, color_balance)

            if self.invert_colors:
                image = invert_image(image)

            self.boolmatrix = self.get_boolmatrix(image)

            if self.crop:
                box = self.boolmatrix.crop()
                image = image.crop(box)

            # Downsize image to width (ascii_width * quality)
            max_width = ascii_width * quality
            if image.width > max_width:
                image = image.resize((max_width, int((max_width / image.width) * image.height)))
                self.boolmatrix = self.get_boolmatrix(image)

            self.source_width, self.source_height = image.width, image.height

            # Save colours
            if self.color:
                default = (0,) * len(image.getbands())
                self.colormatrix = Matrix(image.width, image.height, default, list(image.getdata()))

        # Each character will represent an image section this large
        self.section_width = int(self.source_width / ascii_width) or 1
        self.section_height = int(self.section_width * ascii_ratio) or 1

        self.init_shapes()

    def get_boolmatrix(self, image: Image.Image) -> Matrix[bool]:
        mono = image.convert("1", dither=Image.NONE)
        if self.invert:
            monodata = [v == 0 for v in list(mono.getdata())]
        else:
            monodata = [v != 0 for v in list(mono.getdata())]
        if image.mode == "RGBA":
            # Transparent pixels = False
            for idx, pixel in enumerate(list(image.getdata())):
                if pixel[-1] == 0:
                    monodata[idx] = False
        return Matrix(mono.width, mono.height, False, monodata)

    def init_shape(self, char: str, *points: Tuple[SupportsFloat, SupportsFloat]) -> Shape:
        return Shape(char, *points).init(self.section_width, self.section_height)

    def init_shapes(self):
        """
        Ordering is relevant for performance; start with completely filled and
        completely empty shapes, then try and order them by size of filled
        area (smallest first).
        """
        self.shapes = [
            self.init_shape(EMPTY_CHARACTER, (0, 0)),
            self.init_shape("$", (0, 0), (1, 0), (1, 1), (0, 1)),
            self.init_shape(".", (0, 0.8), (1, 0.8), (1, 1), (0, 1)),
            self.init_shape("°", (0, 0), (1, 0), (1, 0.3), (0, 0.3)),
            self.init_shape("o", (0, 0.5), (1, 0.5), (1, 1), (0, 1)),
            self.init_shape("*", (0, 0), (1, 0), (1, 0.5), (0, 0.5)),
            self.init_shape("b", (0, 0), (1, 1), (0, 1)),
            self.init_shape("d", (1, 0), (1, 1), (0, 1)),
            self.init_shape("P", (0, 0), (1, 0), (0, 1)),
            self.init_shape("?", (0, 0), (1, 0), (1, 1)),
        ]

    def convert(self):
        """
        Divides image into (self.section_width, self.section_height) sized
        sections, or more specifically: extracts boolean matrices for each of
        those sections. Then gets the most suitable ASCII character for
        each section and concatenates them together into an ASCII image.
        """
        rows = []
        last_color_char = None
        for start_y in range(0, self.source_height, self.section_height):
            row = ""
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
                        if pixel_value and self.color:
                            section_colors.append(self.colormatrix[start_y + y][start_x + x])
                if section:
                    if self.color and section_colors:
                        color_value = [
                            mean([c[idx] for c in section_colors])
                            for idx in range(3)
                        ]
                        color = Color(*color_value)
                        color_char = self.color_converter.from_rgb(color)
                        if color_char and color_char != last_color_char:
                            row += color_char
                            last_color_char = color_char
                    row += self.get_char(section)
            rows.append(row)
        output = "\n".join(rows)
        return output

    def get_char(self, section_matrix: Matrix) -> str:
        chars = []  # list of (char, likeness) tuples
        for shape in self.shapes:
            likeness = shape.likeness(section_matrix)
            if likeness > self.min_likeness:
                return shape.char
            chars.append((shape.char, likeness))
        return max(chars, key=lambda c: c[1])[0]
