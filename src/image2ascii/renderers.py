import sys
from abc import ABC, abstractmethod
from collections.abc import Iterator
from io import StringIO
from pathlib import Path
from typing import TYPE_CHECKING, Any, TextIO

from PIL import Image, ImageDraw, ImageFont

from image2ascii.color import ANSI_RESET_ALL, ANSI_RESET_FG
from image2ascii.geometry import EmptyShape, SizeF
from image2ascii.output import (
    BackgroundEnd,
    BackgroundStart,
    Character,
    ColorEnd,
    ColorStart,
    HasBackground,
    Linebreak,
    OutputAtom,
    OutputEnd,
    OutputStart,
    RowEnd,
    RowStart,
)
from image2ascii.timing import timer


if TYPE_CHECKING:
    from image2ascii.color import Color
    from image2ascii.geometry import Size


class AbstractRenderer(ABC):
    original_ratio: float
    size_chars: "Size"

    @timer
    def render(self, atom_iterator: Iterator[OutputAtom]) -> Any:
        for atom in atom_iterator:
            self.render_atom(atom)

    @abstractmethod
    def render_atom(self, atom: OutputAtom) -> Any:
        ...

    @timer
    def start(self, original_ratio: float, size_chars: "Size"):
        self.original_ratio = original_ratio
        self.size_chars = size_chars


class AbstractStringRenderer(AbstractRenderer, ABC):
    def __init__(self, outstream: TextIO = sys.stdout):
        self.outstream = outstream

    @timer
    def output(self, value: str):
        self.outstream.write(value)


class ConsoleRenderer(AbstractStringRenderer):
    HORIZONTAL_LINE = "─"    # alt: ⎺⎽⎯‾─
    VERTICAL_LINE = "⎜"      # alt: ⎜⎟⎢⎥⎪│
    UPPER_LEFT_CORNER = "┌"  # alt: ⎾⎡┌
    UPPER_RIGHT_CORNER = "┐" # alt: ⏋⎤┐
    LOWER_LEFT_CORNER = "└"  # alt: ⎿⎣└
    LOWER_RIGHT_CORNER = "┘" # alt: ⏌⎦┘

    width_with_margins: int

    @timer
    def __init__(
        self,
        outstream: TextIO = sys.stdout,
        margins: int = 0,
        border: bool = False,
        border_color: "Color | None" = None,
    ):
        super().__init__(outstream)
        self.horizontal_margins = margins
        self.margins = margins
        self.border = border
        self.border_color = border_color

    @timer
    def on_output_end(self, atom: HasBackground):
        for _ in range(int(self.margins / 2)):
            self.output_line_break()
            self.on_row_start(atom)
            self.output(" " * self.size_chars.width)
            self.on_row_end(atom)
        if self.border:
            self.output_line_break()
            self.output_lower_border(atom)
        self.output_line_break()

    @timer
    def on_output_start(self, atom: HasBackground):
        self.width_with_margins = self.size_chars.width + (self.margins * 2)

        if atom.background:
            self.output(atom.background.ansi_background)

        if self.border:
            self.output_upper_border()
            self.output_line_break()

        for _ in range(int(self.margins / 2)):
            self.on_row_start(atom)
            self.output(" " * self.size_chars.width)
            self.on_row_end(atom)
            self.output_line_break()

    @timer
    def on_row_end(self, atom: HasBackground):
        if self.margins:
            self.output(ANSI_RESET_FG)
            if atom.background:
                self.output(atom.background.ansi_background)
            self.output(" " * self.margins)
        if self.border:
            self.output_color(self.border_color)
            self.output(self.VERTICAL_LINE)

    @timer
    def on_row_start(self, atom: HasBackground):
        if atom.background:
            self.output(atom.background.ansi_background)
        if self.border:
            self.output_color(self.border_color)
            self.output(self.VERTICAL_LINE)
        if self.margins:
            self.output(ANSI_RESET_FG)
            self.output(" " * self.margins)

    @timer
    def output_color(self, color: "Color | None"):
        if color:
            self.output(color.ansi)
        else:
            self.output(ANSI_RESET_FG)

    @timer
    def output_line_break(self):
        # Reset colours at line break, otherwise the rest of the line will be
        # coloured with the chosen background colour.
        self.output(ANSI_RESET_ALL + "\n")

    @timer
    def output_lower_border(self, atom: HasBackground):
        if atom.background:
            self.output(atom.background.ansi_background)
        self.output_color(self.border_color)
        self.output(self.LOWER_LEFT_CORNER)
        self.output(self.HORIZONTAL_LINE * self.width_with_margins)
        self.output(self.LOWER_RIGHT_CORNER)

    @timer
    def output_upper_border(self):
        self.output_color(self.border_color)
        self.output(self.UPPER_LEFT_CORNER)
        self.output(self.HORIZONTAL_LINE * self.width_with_margins)
        self.output(self.UPPER_RIGHT_CORNER)

    @timer
    def render_atom(self, atom: OutputAtom):
        if isinstance(atom, OutputStart):
            self.on_output_start(atom)
        elif isinstance(atom, BackgroundStart):
            self.output(atom.color.ansi_background)
        elif isinstance(atom, ColorStart):
            self.output(atom.color.ansi)
        elif isinstance(atom, Character):
            self.output(atom.char)
        elif isinstance(atom, RowEnd):
            self.on_row_end(atom)
        elif isinstance(atom, Linebreak):
            self.output_line_break()
        elif isinstance(atom, RowStart):
            self.on_row_start(atom)
        elif isinstance(atom, OutputEnd):
            self.on_output_end(atom)

class HTMLRenderer(AbstractStringRenderer):
    def __init__(self):
        super().__init__(StringIO())

    @property
    def html(self) -> str:
        self.outstream.seek(0)
        return self.outstream.read()

    @timer
    def render_atom(self, atom: OutputAtom):
        """TODO: Tags will probably be weirdly nestled."""
        if isinstance(atom, OutputStart):
            if atom.background:
                self.output(f'<pre style="background-color:{atom.background.css}">')
            else:
                self.output("<pre>")
        elif isinstance(atom, ColorStart):
            self.output(f'<span style="color:{atom.color.css}">')
        elif isinstance(atom, ColorEnd):
            self.output("</span>")
        elif isinstance(atom, BackgroundStart):
            self.output(f'<span style="background-color:{atom.color.css}">')
        elif isinstance(atom, BackgroundEnd):
            self.output("</span>")
        elif isinstance(atom, Linebreak):
            self.output("<br>")
        elif isinstance(atom, Character):
            self.output(atom.char)
        elif isinstance(atom, OutputEnd):
            self.output("</pre>")


class ImageRenderer(AbstractRenderer):
    current_background: "Color | None" = None
    current_color: "Color | None" = None
    column_gap: float
    draw: ImageDraw.ImageDraw
    font: ImageFont.FreeTypeFont
    font_size_to_row_ratio = 0.8
    image: Image.Image
    outfile_largest_side: int
    row_gap: float

    @timer
    def __init__(self, outfile_largest_side: int = 1000):
        self.outfile_largest_side = outfile_largest_side
        self.font_path = Path(__file__).parent / "fonts/DejaVuSansMono.ttf"

    @timer
    def on_output_start(self, atom: OutputStart):
        outfile_size = (
            SizeF(self.outfile_largest_side, self.outfile_largest_side)
            .fit_ratio(self.original_ratio)
            .to_size(round_for_ratio=True)
        )

        # Using nice, round integers for gaps, to avoid some weird irregular
        # gaps here and there:
        self.row_gap = int(outfile_size.height / self.size_chars.height)
        self.column_gap = int(outfile_size.width / self.size_chars.width)

        # Then we have to adjust the output size a little:
        outfile_size.width = self.column_gap * self.size_chars.width
        outfile_size.height = self.row_gap * self.size_chars.height

        self.font = ImageFont.truetype(str(self.font_path), size=self.row_gap * self.font_size_to_row_ratio)
        self.image = Image.new(
            mode="RGBA",
            size=outfile_size.tuple,
            color=atom.background.rgba_tuple if atom.background else 0,
        )
        self.draw = ImageDraw.Draw(self.image)

    @timer
    def render_atom(self, atom: OutputAtom):
        if isinstance(atom, OutputStart):
            self.on_output_start(atom)
        elif isinstance(atom, BackgroundStart):
            self.current_background = atom.color
        elif isinstance(atom, BackgroundEnd):
            self.current_background = None
        elif isinstance(atom, ColorStart):
            self.current_color = atom.color
        elif isinstance(atom, ColorEnd):
            self.current_color = None
        elif isinstance(atom, Character):
            if not isinstance(atom.shape, EmptyShape):
                if self.current_background:
                    left = atom.column * self.column_gap
                    top = atom.row * self.row_gap
                    self.draw.rectangle(
                        xy=[(left, top), (left + self.column_gap, top + self.row_gap)],
                        fill=self.current_background.rgba_tuple,
                    )

                self.draw.text(
                    xy=(atom.column * self.column_gap, atom.row * self.row_gap),
                    text=atom.char,
                    font=self.font,
                    fill=self.current_color.rgba_tuple if self.current_color else (0xff, 0xff, 0xff, 0xff),
                )
