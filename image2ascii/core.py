#!/usr/bin/env python3

import functools
import time
from typing import Dict, List, Optional, Tuple, Type

import numpy as np
from PIL import Image, ImageEnhance, ImageOps
from werkzeug.datastructures import FileStorage

from image2ascii import (
    DEFAULT_ASCII_RATIO, DEFAULT_ASCII_WIDTH, DEFAULT_MIN_LIKENESS, DEFAULT_QUALITY, EMPTY_CHARACTER, FILLED_CHARACTER,
)
from image2ascii.color import ColorConverter, ColorConverterInvertBW
from image2ascii.geometry import BaseShape, CropBox, EmptyShape, FilledShape, PolygonShape, get_crop_box
from image2ascii.output import ANSIFormatter, BaseFormatter, HTMLFormatter, Output

# Mnemonics for colour array indices
# (red, green, blue, alpha, saturation, luminance, visible):
R, G, B, A, S, L, V = 0, 1, 2, 3, 4, 5, 6


def timer(func):
    @functools.wraps(func)
    def wrapper(self, *args, **kwargs):
        if not self.debug:
            return func(self, *args, **kwargs)
        start_time = time.monotonic()
        ret = func(self, *args, **kwargs)
        elapsed_time = time.monotonic() - start_time
        self.timing.append((func.__name__, elapsed_time))
        return ret
    return wrapper


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
    _swap_bw: bool = False

    filename: Optional[str] = None
    formatter_class: Type[BaseFormatter] = ANSIFormatter
    image: Optional[Image.Image] = None
    output: Optional[Output] = None

    debug: bool
    shapes: List[BaseShape]
    timing: List

    def __init__(self, file=None, debug: bool = False):
        self.debug = debug
        self.timing = []
        if file is not None:
            self.load(file)

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

    @property
    def swap_bw(self) -> bool:
        return self._swap_bw

    @swap_bw.setter
    def swap_bw(self, value: bool):
        if value != self._swap_bw:
            self._swap_bw = value
            self.color_converter_class = ColorConverterInvertBW if value else ColorConverter
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
            self.swap_bw = swap_bw
        return self

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
        return self

    def quality_settings(self, quality: Optional[int] = None, min_likeness: Optional[float] = None):
        if quality is not None:
            self.quality = quality
        if min_likeness is not None:
            self.min_likeness = min_likeness
        return self

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
        return self

    def set_output_format(self, value: str):
        if value == "html":
            self.formatter_class = HTMLFormatter
        elif value in ("ascii", "ansi"):
            self.formatter_class = ANSIFormatter
        return self

    """
    THE REST OF THE JAZZ
    """
    @timer
    def do_crop(self, image: Image.Image) -> Image.Image:
        image = self.do_resize(image)
        if self.crop:
            matrix = self.get_matrix(image)
            # Expecting the last value to be a "white" boolean
            boolmatrix = matrix[:, :, -1]
            cropbox = get_crop_box(boolmatrix)
            image = image.crop(cropbox)
        return image

    @timer
    def do_enhance(self, image: Image.Image) -> Image.Image:
        if self.contrast != 1.0:
            image = ImageEnhance.Contrast(image).enhance(self.contrast)
        if self.brightness != 1.0:
            image = ImageEnhance.Brightness(image).enhance(self.brightness)
        if self.color_balance != 1.0:
            image = ImageEnhance.Color(image).enhance(self.color_balance)
        return image

    @timer
    def do_invert(self, image: Image.Image) -> Image.Image:
        """
        For some reason, PIL.ImageOps.invert() does not support RGBA.
        This implementation leaves the alpha channel as it is.
        """
        if self.invert_colors:
            if image.mode == "RGBA":
                lut = [i for i in range(0xff, -1, -1)] * 3 + [i for i in range(0xff + 1)]
                return image.point(lut)
            return ImageOps.invert(image)
        return image

    @timer
    def do_resize(self, image: Image.Image) -> Image.Image:
        """
        Resize image to a multiple of the sizes of the sections it will be
        divided into, with a width not exceeding self.ascii_width *
        self.quality.
        """
        end_width = self.ascii_width * self.quality

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

        return image

    def get_section_size(self, image: Image.Image) -> Tuple[int, int]:
        section_width = int(image.width / self.ascii_width) or 1
        return section_width, int(section_width * self.ascii_ratio) or 1

    @timer
    def get_char(self, nonzero_coords: List[Tuple[int, int]]) -> str:
        chars = []  # list of (char, likeness) tuples

        for shape in self.shapes:
            likeness = shape.likeness(nonzero_coords)
            if likeness > self.min_likeness:
                return shape.char
            chars.append((shape.char, likeness))
        return max(chars, key=lambda c: c[1])[0]

    @timer
    def get_matrix(self, image: Image.Image):
        """
        If self.fill_all: Only transparent pixels (more precisely: those with
            alpha < 0x80) will be considered unfilled. Otherwise,
            filled/unfilled status will be a result of transparency AND
            whatever a conversion to monochrome spits out.
        If self.invert: Reverses the filled/unfilled status for all pixels.
        """
        MIN, MAX = 0, 1  # Mnemonics for the minmax array

        if not image.width or not image.height:
            return np.empty((0, 0, 0))

        assert image.mode == "RGBA", "Image mode must be RGBA"

        arr = np.empty((image.width * image.height, 7), dtype=np.uint8)

        # Fill first 4 values with R, G, B, A
        arr[:, :A + 1] = np.array(image.getdata())

        # Array of (min colour value, max colour value) for each RGB colour,
        # converted to percentages. 100 % of course represents 255.
        minmax = np.empty((image.width * image.height, 2))
        minmax[:, MIN] = arr[:, :B + 1].min(axis=1) / 0xff * 100
        minmax[:, MAX] = arr[:, :B + 1].max(axis=1) / 0xff * 100

        # Luminance = (min + max) / 2, also percentage
        arr[:, L] = minmax.mean(axis=1)

        # Saturation = (max - min) / (max + min), converted to percent
        arr[:, S] = np.divide(
            minmax[:, MAX] - minmax[:, MIN], minmax[:, MAX] + minmax[:, MIN],
            out=np.zeros((image.width * image.height,)),
            where=minmax[:, MAX] > 0  # avoid division by zero
        ) * 100

        # Now to find the W (white) values:
        if self.fill_all:
            # Pos W becomes 0 if pos A < 0x80, 1 otherwise
            arr[:, V] = arr[:, A] >= 0x80
        else:
            # Calculate W values according to algorithm below, but alpha
            # takes precedence (if A < 0x80, W is 0).
            # https://pillow.readthedocs.io/en/stable/reference/Image.html#PIL.Image.Image.convert
            arr[:, V] = np.all((
                arr[:, A] >= 0x80,
                arr[:, R] * 0.299 + arr[:, G] * 0.587 + arr[:, B] * 0.114 >= 0x80
            ), axis=0)

        if self.invert:
            arr[:, V] = arr[:, V] == 0

        # Reshape to image.height rows and image.width columns
        return arr.reshape(image.height, image.width, 7)

    @timer
    def init_shapes(self, section_width: int, section_height: int):
        """
        Ordering is relevant for performance; start with completely filled and
        completely empty shapes, then order them by which character you deem
        to be more desirable.
        """
        self.shapes = [
            EmptyShape(char=EMPTY_CHARACTER, width=section_width, height=section_height),
            FilledShape(char=FILLED_CHARACTER, width=section_width, height=section_height),
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

    @timer
    def load(self, file):
        if isinstance(file, str):
            self.filename = file
        elif isinstance(file, FileStorage):
            self.filename = file.filename
        elif hasattr(file, "name") and isinstance(file.name, str):
            self.filename = file.name

        with Image.open(file) as image:
            image.load()
        if image.mode != "RGBA":
            image = image.convert("RGBA")
        # Downsize original if it's ridiculously large
        if image.width > 2000 or image.height > 2000:
            factor = 2000 / max(image.width, image.height)
            image = image.resize((round(image.width * factor), round(image.height * factor)))
        if image != self.image:
            self.image = image
            self.reset()
        return self

    @timer
    def prepare_image(self) -> Tuple[int, int, Image.Image]:
        """
        Returns: section_width, section_height, prepared image
        """
        if self.image is None:
            raise ValueError("You need to run .load(file)")
        image = self.do_enhance(self.image)
        image = self.do_invert(image)
        image = self.do_crop(image)
        image = self.do_resize(image)
        section_width, section_height = self.get_section_size(image)
        self.init_shapes(section_width, section_height)
        return section_width, section_height, image

    @timer
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
            matrix = self.get_matrix(image)

            if self.color:
                last_color = None
                color_converter = self.color_converter_class()

            for start_y in range(0, image.height, section_height):
                for start_x in range(0, image.width, section_width):
                    section = matrix[start_y:start_y + section_height, start_x:start_x + section_width]
                    if self.color:
                        # Create a 2-d array of points:
                        points = section.reshape(section_width * section_height, section.shape[-1])
                        # Filter for points where visibility is 1:
                        section_colors = points[points[:, V] > 0]
                        if section_colors.size:
                            # Get median value and reduce it to array of
                            # R, G, B, S, L values:
                            color_value = np.median(section_colors, axis=0)[np.array([R, G, B, S, L])]
                            new_color = color_converter.from_array(color_value)
                            if new_color != last_color:
                                self.output.add_color(new_color)
                                last_color = new_color
                    nonzero = np.nonzero(section[:, :, -1])
                    if nonzero[0].size:
                        # 1-indexed (x, y) coordinates of filled points:
                        nonzero_coords = list(zip(nonzero[1] + 1, nonzero[0] + 1))
                        char = self.get_char(nonzero_coords)
                    else:
                        char = EMPTY_CHARACTER
                    self.output.add_text(char)
                self.output.add_br()
        return self.formatter_class(self.output).render()

    def reset(self):
        self.output = None

    def summarize_timing(self):
        result: Dict[str, Tuple[int, float]] = {}
        for funcname, timing in self.timing:
            if funcname in result:
                result[funcname] = (result[funcname][0] + 1, result[funcname][1] + timing)
            else:
                result[funcname] = (1, timing)
        return result
