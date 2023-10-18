#!/usr/bin/env python3

from typing import List, Optional, Tuple

import numpy as np
from PIL import Image, ImageEnhance, ImageOps

from image2ascii.color import BaseColorConverter
from image2ascii.config import Config, ConfigListener
from image2ascii.geometry import BaseShape, CropBox, EmptyShape, FilledShape, PolygonShape
from image2ascii.output import Output
from image2ascii.utils import timer

# Mnemonics for colour array indices
# (red, green, blue, alpha, visibility, hue, saturation, value)
# H, S, and Va are currently not used, though.
R, G, B, A, Vi, H, S, Va = range(8)

EMPTY_CHARACTER = " "
FILLED_CHARACTER = "$"


class Image2ASCII(ConfigListener):
    _config: Config

    image: Optional[Image.Image] = None
    output: Optional[Output] = None

    shapes: List[BaseShape]

    def __init__(
        self,
        file=None,
        config: Optional[Config] = None,
    ):
        if config is None:
            config = Config.from_default_files()
        config.add_listener(self)
        self._config = config
        if file is not None:
            self.load(file)

    def __hash__(self) -> int:
        return hash(self.image)

    ### PROPERTIES ############################################################

    @property
    def config(self) -> Config:
        return self._config

    ### CONVENIENCE SETTINGS METHODS ##########################################

    def color_settings(
        self,
        color: Optional[bool] = None,
        invert: Optional[bool] = None,
        negative: Optional[bool] = None,
        fill_all: Optional[bool] = None,
    ):
        if color is not None:
            self.config.color = color
        if invert is not None:
            self.config.invert = invert
        if negative is not None:
            self.config.negative = negative
        if fill_all is not None:
            self.config.fill_all = fill_all
        return self

    def enhancement_settings(
        self,
        contrast: Optional[float] = None,
        brightness: Optional[float] = None,
        color_balance: Optional[float] = None
    ):
        if contrast is not None:
            self.config.contrast = contrast
        if brightness is not None:
            self.config.brightness = brightness
        if color_balance is not None:
            self.config.color_balance = color_balance
        return self

    def quality_settings(self, quality: Optional[int] = None, min_likeness: Optional[float] = None):
        if quality is not None:
            self.config.quality = quality
        if min_likeness is not None:
            self.config.min_likeness = min_likeness
        return self

    def size_settings(
        self,
        max_height: Optional[int] = None,
        width: Optional[int] = None,
        ratio: Optional[float] = None,
        crop: Optional[bool] = None
    ):
        """
        To explicitly set max height to None, if it has previously been set to
        something else, do `i2a.config.max_height = None` instead.
        """
        if max_height is not None:
            self.config.max_height = max_height
        if width is not None:
            self.config.width = width
        if ratio is not None:
            self.config.ratio = ratio
        if crop is not None:
            self.config.crop = crop
        return self

    ### THE REST OF THE JAZZ ##################################################

    def config_changed(self, key, value):
        self.reset()

    @timer
    def do_crop(self, image: Image.Image, matrix: np.ndarray) -> Tuple[Image.Image, bool]:
        """
        `image` does not necessarily have the same dimensions as `matrix`, so
        we transpose the cropbox before doing the actual cropping.
        """
        if self.config.crop:
            ratio = image.height / matrix.shape[0]
            cropbox = self.get_crop_box(matrix)
            if cropbox != CropBox(0, 0, matrix.shape[1], matrix.shape[0]):
                cropbox = CropBox(*[round(v * ratio) for v in cropbox])
                image = image.crop(cropbox)
                return image, True
        return image, False

    @timer
    def do_enhance(self, image: Image.Image) -> Image.Image:
        if self.config.contrast != 1.0:
            image = ImageEnhance.Contrast(image).enhance(self.config.contrast)
        if self.config.brightness != 1.0:
            image = ImageEnhance.Brightness(image).enhance(self.config.brightness)
        if self.config.color_balance != 1.0:
            image = ImageEnhance.Color(image).enhance(self.config.color_balance)
        return image

    @timer
    def do_negative(self, image: Image.Image) -> Image.Image:
        """
        For some reason, PIL.ImageOps.invert() does not support RGBA.
        This implementation leaves the alpha channel as it is.
        """
        if self.config.negative:
            if image.mode == "RGBA":
                lut = list(range(0xff, -1, -1)) * 3 + list(range(0xff + 1))
                return image.point(lut)
            return ImageOps.invert(image)
        return image

    @timer
    def do_resize(self, image: Image.Image) -> Image.Image:
        """
        Resize image to a multiple of the sizes of the sections it will be
        divided into, with a width not exceeding (self.config.width *
        self.config.quality), and a height not exceeding
        (self.config.max_height * self.config.quality * self.config.ratio), in
        case self.config.max_height is not None.

        Note: A small value for self.config.max_height will not make the output
        narrower, it will only make it less detailed, as it will decrease the
        size of the source image before processing. It is not intended for
        shrinking the output but to reduce CPU load for very "thin" images.
        """
        end_width = min(image.width, self.config.width * self.config.quality)

        if self.config.max_height is not None:
            max_height = round(self.config.max_height * self.config.quality * self.config.ratio)
            if (image.height * self.config.ratio * (end_width / image.width)) > max_height:
                # Image is still too tall after adjusting width; decrease
                # end width so end height == max height
                end_width = round(image.width * (max_height / image.height) / self.config.ratio)

        # Round to the nearest multiple of self.config.width if needed
        if end_width % self.config.width:
            if end_width > self.config.width and \
                    end_width % self.config.width < self.config.width * 0.25:
                # We're over self.config.width and arbitrarily close to the
                # multiple below; shrink
                end_width -= end_width % self.config.width
            else:
                # Otherwise, grow
                end_width += self.config.width - end_width % self.config.width

        if image.width != end_width:
            image = image.resize((end_width, round((end_width / image.width) * image.height)), resample=Image.NEAREST)

        # Each character will represent an image section this large
        section_width = int(image.width / self.config.width) or 1
        section_height = int(section_width * self.config.ratio) or 1

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

    @timer
    def get_char(self, nonzero_coords: List[Tuple[int, int]]) -> str:
        chars = []  # list of (char, likeness) tuples

        for shape in self.shapes:
            likeness = shape.likeness(nonzero_coords)
            if likeness > self.config.min_likeness:
                return shape.char
            chars.append((shape.char, likeness))
        return max(chars, key=lambda c: c[1])[0]

    @timer
    def get_crop_box(self, matrix: np.ndarray) -> CropBox:
        height, width, _ = matrix.shape
        left = 0
        upper = 0
        right = 0
        lower = 0

        for left in range(width):
            if matrix[:, left, Vi].any():
                break

        for upper in range(height):
            if matrix[upper, :, Vi].any():
                break

        for right in range(width, left, -1):
            if matrix[:, right - 1, Vi].any():
                break

        for lower in range(height, upper, -1):
            if matrix[lower - 1, :, Vi].any():
                break

        return CropBox(left, upper, right, lower)

    @timer
    def get_matrix(self, image: Image.Image):
        """
        If self.config.fill_all: Only transparent pixels (more precisely:
            those with alpha < 0x80) will be considered unfilled. Otherwise,
            filled/unfilled status will be a result of transparency AND
            whatever a conversion to monochrome spits out.
        If self.config.invert: Reverses the filled/unfilled status for all
            pixels.
        Returns: 3-d array with shape = (image height, image width, 5), where
            the last axis contains the following values for each pixel:
            (red, green, blue, alpha, visibility)
        """
        if not image.width or not image.height:
            return np.empty((0, 0, 5))

        assert image.mode == "RGBA", "Image mode must be RGBA"

        arr = np.empty((image.width * image.height, 5), dtype=np.uint64)

        # Fill first 4 values with R, G, B, A
        arr[:, :A + 1] = np.array(image.getdata())

        # Fill the next 3 with H, S, Va
        # arr[:, H:Va + 1] = rgb_to_hsv(arr[:, :B + 1])

        # Now to find the Vi (visibility) values:
        if self.config.fill_all:
            # All chars are visible except transparent (A < 0x80) ones:
            arr[:, Vi] = arr[:, A] >= 0x80
        else:
            # Calculate perceived brightness per algorithm:
            # https://pillow.readthedocs.io/en/stable/reference/Image.html#PIL.Image.Image.convert
            perceived_brightness = arr[:, R] * 0.299 + arr[:, G] * 0.587 + arr[:, B] * 0.114

            # Transparency (A < 0x80) still takes precedence:
            if not self.config.invert:
                arr[:, Vi] = np.all((arr[:, A] >= 0x80, perceived_brightness >= 0x80), axis=0)
            else:
                # If self.config.invert, make chars visible that have a
                # perceived brightness _less_ than 0x80:
                arr[:, Vi] = np.all((arr[:, A] >= 0x80, perceived_brightness < 0x80), axis=0)

        # Reshape to image.height rows and image.width columns
        return arr.reshape(image.height, image.width, 5)  # pylint: disable=too-many-function-args

    @timer
    def get_section_color(self, section: np.ndarray, converter: Optional[BaseColorConverter]) -> Optional[np.ndarray]:
        # Generate a 2-d array of colour data for points where V > 0:
        if converter is not None:
            colors = section[section[:, :, Vi] > 0]
            if colors.size:
                color_arr = np.median(colors[:, np.array([R, G, B])], axis=0, out=np.empty(3, dtype=np.uint64))
                return converter.closest(color_arr)
        return None

    def get_section_size(self, image: Image.Image) -> Tuple[int, int]:
        section_width = int(image.width / self.config.width) or 1
        return section_width, int(section_width * self.config.ratio) or 1

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
        with Image.open(file) as image:
            image.load()
        if image.mode != "RGBA":
            image = image.convert("RGBA")
        # Downsize original if it's too large
        # if image.width > 2000 or image.height > 2000:
        if image.width > self.config.max_original_size or image.height > self.config.max_original_size:
            factor = self.config.max_original_size / max(image.width, image.height)
            image = image.resize((round(image.width * factor), round(image.height * factor)))
        if image != self.image:
            self.image = image
            self.reset()
        return self

    @timer
    def prepare_image(self) -> Tuple[Image.Image, np.ndarray]:
        """
        There is a logic to the order of execution here; first of all, we need
        a get_matrix() in order to do_crop(). That matrix has to be generated
        from an image of a reasonable size, otherwise it would take an
        inordinate amount of time. However, we also want to do_crop() on a
        non-resized image, lest the resulting image becomes unnecessarily
        small, and hence the output quality is less than expected.

        Also, if any cropping was done, we need to do_resize() once again,
        since the cropping probably made the image dimensions unsuitable (i.e.
        height and/or width not being a multiple of self.config.quality).

        The actual cropping and resizing takes a miniscule amount of time,
        though, so it's not a real problem.
        """
        if self.image is None:
            raise ValueError("You need to run .load(file)")

        image = self.image.copy()

        image = self.do_enhance(image)
        image = self.do_negative(image)

        resized_image = self.do_resize(image)
        matrix = self.get_matrix(resized_image)

        image, cropped = self.do_crop(image, matrix)
        if cropped:
            image = self.do_resize(image)
            matrix = self.get_matrix(image)
        else:
            image = resized_image

        return image, matrix

    @timer
    def render(self):
        """
        Divides image into (self.section_width, self.section_height) sized
        sections, or more specifically: extracts boolean matrices for each of
        those sections. Then gets the most suitable ASCII character for
        each section and concatenates them together. Then renders the result
        in the selected format.
        """
        formatter = self.config.get_formatter()

        if self.output is None:
            image, matrix = self.prepare_image()
            section_width, section_height = self.get_section_size(image)
            self.init_shapes(section_width, section_height)
            self.output = Output()
            last_color = None

            for start_y in range(0, image.height, section_height):
                for start_x in range(0, image.width, section_width):
                    section = matrix[start_y:start_y + section_height, start_x:start_x + section_width]
                    if self.config.color:
                        new_color = self.get_section_color(section, formatter.color_converter)
                        if new_color is not None and (last_color is None or not np.all(new_color == last_color)):
                            self.output.add_color(new_color)
                            last_color = new_color
                    nonzero = np.nonzero(section[:, :, -1])
                    if not nonzero[0].size:
                        # Micro-optimization
                        char = EMPTY_CHARACTER
                    else:
                        # 1-indexed (x, y) coordinates of filled points:
                        nonzero_coords = list(zip(nonzero[1] + 1, nonzero[0] + 1))
                        char = self.get_char(nonzero_coords)
                    self.output.add_text(char)
                self.output.add_br()
        return formatter.render(self.output)

    def reset(self):
        self.output = None
