from typing import Dict, List, Tuple

from image2ascii.color import Color
from image2ascii.utils import timer


class Output:
    format: str
    rows: List[str]
    colors: Dict[Tuple[int, int], Color]  # {(x, y): color}

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
    def add_color(self, color: Color):
        self.colors[(self.col_ptr, self.row_ptr)] = color


class BaseFormatter:
    name: str
    br = "\n"

    def __init__(self, output: Output):
        self.output = output

    @timer
    def render(self) -> str:
        output = ""
        for row_idx, row in enumerate(self.output.rows):
            if row_idx > 0:
                output += self.br
            for col_idx, char in enumerate(row):
                if (col_idx, row_idx) in self.output.colors:
                    output += self.render_color(self.output.colors[(col_idx, row_idx)])
                output += char
        return output

    @timer
    def render_color(self, color: Color) -> str:
        return ""


class ANSIFormatter(BaseFormatter):
    name = "ansi"

    @timer
    def render_color(self, color: Color):
        return color.ansi


class HTMLFormatter(BaseFormatter):
    name = "html"
    br = "<br>"
    open_span = False

    @timer
    def render(self):
        self.open_span = False
        output = "<pre>"
        output += super().render()
        if self.open_span:
            output += "</span>"
            self.open_span = False
        output += "</pre>"
        return output

    @timer
    def render_color(self, color: Color):
        output = ""
        if self.open_span:
            output += "</span>"
        output += f"<span style=\"color:{color.hex}\">"
        self.open_span = True
        return output
