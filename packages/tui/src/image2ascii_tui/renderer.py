import itertools

from textual.color import Color as TextualColor
from textual.content import Content, Span
from textual.style import Style

from image2ascii.color import Color
from image2ascii.output import (
    BackgroundEnd,
    BackgroundStart,
    Character,
    ColorEnd,
    ColorStart,
    Linebreak,
    OutputAtom,
    RowEnd,
    RowStart,
)
from image2ascii.renderers import AbstractRenderer


class TextualRenderer(AbstractRenderer):
    def __init__(self):
        self.color_starts: list[ColorStart] = []
        self.color_ends: list[ColorEnd] = []
        self.background_starts: list[BackgroundStart] = []
        self.background_ends: list[BackgroundEnd] = []
        self.text = ""

    def coords_to_strpos(self, column: int, row: int):
        # Including linebreak:
        row_length = self.size_chars.width + 1
        return (row_length * row) + column

    @staticmethod
    def color_to_textual(color: Color):
        return TextualColor(r=color.r, g=color.g, b=color.b)

    def render_content(self) -> Content:
        spans: list[Span] = []
        # color_starts = sorted(self.color_starts, key=lambda a: self.coords_to_strpos(a.column, a.row))
        # color_ends = sorted(self.color_ends, key=lambda a: self.coords_to_strpos(a.column, a.row))
        color_starts = self.color_starts
        color_ends = self.color_ends
        background_starts = sorted(self.background_starts, key=lambda a: self.coords_to_strpos(a.column, a.row))
        background_ends = sorted(self.background_ends, key=lambda a: self.coords_to_strpos(a.column, a.row))

        for start, end in itertools.zip_longest(color_starts, color_ends, fillvalue=None):
            if start is None:
                break
            span_end = self.coords_to_strpos(end.column, end.row) if end is not None else len(self.text)
            spans.append(
                Span(
                    start=self.coords_to_strpos(start.column, start.row),
                    end=span_end,
                    style=Style(foreground=self.color_to_textual(start.color)),
                )
            )

        for start, end in itertools.zip_longest(background_starts, background_ends, fillvalue=None):
            if start is None:
                break
            span_end = self.coords_to_strpos(end.column, end.row) if end is not None else len(self.text)
            spans.append(
                Span(
                    start=self.coords_to_strpos(start.column, start.row),
                    end=span_end,
                    style=Style(background=self.color_to_textual(start.color)),
                )
            )

        return Content(text=self.text, spans=spans)

    def render_atom(self, atom: OutputAtom):
        line = ""
        current_background: Color | None = None
        current_color: Color | None = None

        if isinstance(atom, BackgroundStart):
            current_background = atom.color
            line += f"[on {atom.color.css}]"
            self.background_starts.append(atom)
        elif isinstance(atom, BackgroundEnd):
            current_background = None
            line += "[/on]"
            self.background_ends.append(atom)
        elif isinstance(atom, ColorStart):
            current_color = atom.color
            line += f"[{atom.color.css}]"
            self.color_starts.append(atom)
        elif isinstance(atom, ColorEnd):
            current_color = None
            line += "[/]"
            self.color_ends.append(atom)
        elif isinstance(atom, Character):
            line += atom.char
            self.text += atom.char
        elif isinstance(atom, Linebreak):
            self.text += "\n"
        elif isinstance(atom, RowEnd):
            if current_color:
                line += "[/]"
            if current_background:
                line += "[/on]"
            yield line
            line = ""
        elif isinstance(atom, RowStart):
            if current_background:
                line += f"[on {current_background.css}]"
            if current_color:
                line += f"[{current_color.css}]"
