from typing import Dict, List, Optional, Tuple, Type

import numpy as np

from image2ascii.color import ANSIColorConverter, BaseColorConverter, HTMLFullRGBColorConverter
from image2ascii.utils import timer


class Output:
    format: str
    rows: List[str]
    colors: Dict[Tuple[int, int], np.ndarray]  # {(x, y): color}

    def __init__(self):
        self.rows = []
        self.colors = {}
        self.row_ptr = 0
        self.col_ptr = 0

    @timer
    def add_text(self, text: str):
        if len(self.rows) == self.row_ptr:
            self.rows.append(text)
        else:
            self.rows[self.row_ptr] += text
        self.col_ptr += len(text)

    @timer
    def add_br(self):
        self.row_ptr += 1
        self.col_ptr = 0

    @timer
    def add_color(self, color: np.ndarray):
        self.colors[(self.col_ptr, self.row_ptr)] = color


class BaseFormatter:
    name: str
    br = "\n"
    color_converter: BaseColorConverter
    color_converter_class: Type[BaseColorConverter]

    def __init__(self, color_converter_class: Optional[Type[BaseColorConverter]] = None):
        if color_converter_class is not None:
            self.color_converter_class = color_converter_class
        self.color_converter = self.color_converter_class()

    @timer
    def render(self, output: Output) -> str:
        ret = ""

        for row_idx, row in enumerate(output.rows):
            if row_idx > 0:
                ret += self.br
            for col_idx, char in enumerate(row):
                if (col_idx, row_idx) in output.colors:
                    ret += self.render_color(output.colors[(col_idx, row_idx)])
                ret += char
        return ret

    @timer
    def render_color(self, color: np.ndarray) -> str:
        return self.color_converter.to_representation(color)


class ANSIFormatter(BaseFormatter):
    name = "ansi"
    color_converter_class = ANSIColorConverter


class HTMLFormatter(BaseFormatter):
    name = "html"
    br = "<br>"
    open_span = False
    color_converter_class = HTMLFullRGBColorConverter

    @timer
    def render(self, output: Output) -> str:
        self.open_span = False
        ret = "<pre>"
        ret += super().render(output)
        if self.open_span:
            ret += "</span>"
            self.open_span = False
        ret += "</pre>"
        return ret

    @timer
    def render_color(self, color: np.ndarray) -> str:
        output = ""
        if self.open_span:
            output += "</span>"
        output += f"<span style=\"color:{self.color_converter.to_representation(color)}\">"
        self.open_span = True
        return output
