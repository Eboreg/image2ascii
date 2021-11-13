from typing import Dict, List, Optional, Tuple

from image2ascii.color import Color


class BaseFormatter:
    name: str
    br = "\n"

    def render(self, rows: List[str], colors: Optional[Dict[Tuple[int, int], Color]]) -> str:
        output = ""
        for row_idx, row in enumerate(rows):
            if row_idx > 0:
                output += self.br
            for col_idx, char in enumerate(row):
                if colors and (col_idx, row_idx) in colors:
                    output += self.render_color(colors[(col_idx, row_idx)])
                output += char
        return output

    def render_color(self, color: Color) -> str:
        return ""


class ASCIIFormatter(BaseFormatter):
    name = "ascii"


class ANSIFormatter(BaseFormatter):
    name = "ansi"

    def render_color(self, color: Color):
        return color.ansi


class HTMLFormatter(BaseFormatter):
    name = "html"
    br = "<br>"
    open_span = False

    def render(self, rows, colors):
        self.open_span = False
        output = "<pre>"
        output += super().render(rows, colors)
        if self.open_span:
            output += "</span>"
            self.open_span = False
        output += "</pre>"
        return output

    def render_color(self, color: Color):
        output = ""
        if self.open_span:
            output += "</span>"
        output += f"<span color=\"{color.hex}\">"
        self.open_span = True
        return output


class Output:
    format: str
    rows: List[str]
    colors: Dict[Tuple[int, int], Color]  # {(x, y): color}

    def __init__(self, formatter: Optional[BaseFormatter] = None):
        if formatter is None:
            formatter = ASCIIFormatter()
        self.set_formatter(formatter)
        self.rows = []
        self.colors = {}
        self.row_ptr = 0
        self.col_ptr = 0

    def add_text(self, text: str):
        if len(self.rows) == self.row_ptr:
            self.rows.append(text)
        else:
            self.rows[self.row_ptr] += text
        self.col_ptr += len(text)

    def add_br(self):
        self.row_ptr += 1
        self.col_ptr = 0

    def add_color(self, color: Color):
        self.colors[(self.col_ptr, self.row_ptr)] = color

    def render(self) -> str:
        return self.formatter.render(self.rows, self.colors)

    def set_formatter(self, formatter: BaseFormatter):
        assert isinstance(formatter, BaseFormatter), "Invalid formatter"
        self.formatter = formatter
