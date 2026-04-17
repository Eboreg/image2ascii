import sys
from abc import ABC, abstractmethod
from io import StringIO
from pathlib import Path
from typing import TYPE_CHECKING, ClassVar, TextIO

from PIL import Image, ImageDraw, ImageFont

from image2ascii.color import ANSI_RESET_ALL, ANSI_RESET_FG, Color
from image2ascii.geometry import Size, SizeF
from image2ascii.timing import timer


if TYPE_CHECKING:
    from image2ascii.character import Character


class AbstractRenderer(ABC):
    background: Color | None
    original_ratio: float
    size_chars_rounded: Size
    size_chars: SizeF

    current_color: Color | None = None
    current_row: int | None = None

    def finish(self):
        self.on_finish()

    @abstractmethod
    def on_character(self, character: "Character"): ...

    def on_finish(self): ...

    def on_line_break(self): ...

    def on_new_color(self, color: Color | None, old_color: Color | None = None): ...

    def on_row_end(self): ...

    def on_row_start(self): ...

    def on_start(self): ...

    @timer
    def render_character(self, character: "Character"):
        if character.row != self.current_row:
            if self.current_row is not None:
                self.on_row_end()
                self.on_line_break()
            self.current_row = character.row
            self.on_row_start()

        if character.color != self.current_color:
            self.on_new_color(character.color, self.current_color)
            self.current_color = character.color

        self.on_character(character)

    @timer
    def start(self, original_ratio: float, size_chars: SizeF, background: Color | None = None):
        self.original_ratio = original_ratio
        self.size_chars = size_chars
        self.size_chars_rounded = size_chars.to_size(round_for_ratio=True)
        self.background = background
        self.on_start()


class AbstractStringRenderer(AbstractRenderer, ABC):
    BR: ClassVar[str]

    def __init__(self, outstream: TextIO = sys.stdout):
        self.outstream = outstream

    def on_character(self, character):
        self.output(character.char)

    def on_line_break(self):
        self.output(self.BR)

    @timer
    def output(self, value: str):
        self.outstream.write(value)


class ConsoleRenderer(AbstractStringRenderer):
    BR = "\n"
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
        border_color: Color | None = None,
    ):
        super().__init__(outstream)
        self.horizontal_margins = margins
        self.margins = margins
        self.border = border
        self.border_color = border_color

    @timer
    def on_finish(self):
        self.on_row_end()

        for _ in range(int(self.margins / 2)):
            self.on_line_break()
            self.on_row_start()
            self.output(" " * self.size_chars_rounded.width)
            self.on_row_end()

        if self.border:
            self.on_line_break()
            self.output_lower_border()

        self.output(ANSI_RESET_ALL)

    @timer
    def on_line_break(self):
        # Reset colours at line break, otherwise the rest of the line will be
        # coloured with the chosen background colour.
        self.output(ANSI_RESET_ALL)
        super().on_line_break()

    @timer
    def on_new_color(self, color, old_color=None):
        if color:
            self.output(color.ansi)
        else:
            self.output(ANSI_RESET_FG)

    @timer
    def on_row_end(self):
        if self.margins:
            self.output(ANSI_RESET_FG)
            self.output(" " * self.margins)
        if self.border:
            self.on_new_color(self.border_color)
            self.output(self.VERTICAL_LINE)

    @timer
    def on_row_start(self):
        # Trigger a redraw of foreground colour for next character:
        self.current_color = None
        self.output_bg()

        if self.border:
            self.on_new_color(self.border_color)
            self.output(self.VERTICAL_LINE)
        if self.margins:
            self.output(ANSI_RESET_FG)
            self.output(" " * self.margins)

    @timer
    def on_start(self):
        self.width_with_margins = self.size_chars_rounded.width + (self.margins * 2)

        if self.border:
            self.output_upper_border()
            self.on_line_break()

        for _ in range(int(self.margins / 2)):
            self.on_row_start()
            self.output(" " * self.size_chars_rounded.width)
            self.on_row_end()
            self.on_line_break()

    @timer
    def output_bg(self):
        if self.background:
            self.output(self.background.ansi_background)

    @timer
    def output_lower_border(self):
        self.output_bg()
        self.on_new_color(self.border_color)
        self.output(self.LOWER_LEFT_CORNER)
        self.output(self.HORIZONTAL_LINE * self.width_with_margins)
        self.output(self.LOWER_RIGHT_CORNER)

    @timer
    def output_upper_border(self):
        self.output_bg()
        self.on_new_color(self.border_color)
        self.output(self.UPPER_LEFT_CORNER)
        self.output(self.HORIZONTAL_LINE * self.width_with_margins)
        self.output(self.UPPER_RIGHT_CORNER)


class HTMLRenderer(AbstractStringRenderer):
    BR = "<br>"

    def __init__(self):
        super().__init__(StringIO())

    @property
    def html(self) -> str:
        self.outstream.seek(0)
        return self.outstream.read()

    def on_finish(self):
        if self.current_color:
            self.output("</span>")
        self.output("</pre>")

    def on_new_color(self, color, old_color=None):
        if old_color:
            self.output("</span>")
        if color:
            self.output(f'<span style="color:{color.css}">')

    def on_start(self):
        if self.background:
            self.output(f'<pre style="background-color:{self.background.css}">')
        else:
            self.output("<pre>")


class ImageRenderer(AbstractRenderer):
    image: Image.Image
    draw: ImageDraw.ImageDraw
    font: ImageFont.FreeTypeFont
    outfile_largest_side: int
    row_gap: float
    column_gap: float

    @timer
    def __init__(self, outfile_largest_side: int = 1000):
        self.outfile_largest_side = outfile_largest_side
        self.font_path = Path(__file__).parent / "fonts/DejaVuSansMono.ttf"

    @timer
    def on_character(self, character: "Character"):
        if character.char != " ":
            if character.color:
                fill = character.color.rgba_tuple
            else:
                fill = (0xff, 0xff, 0xff, 0xff)

            self.draw.text(
                xy=(character.column * self.column_gap, character.row * self.row_gap),
                text=character.char,
                font=self.font,
                fill=fill,
            )

    @timer
    def on_start(self):
        outfile_size = (
            Size(self.outfile_largest_side, self.outfile_largest_side)
            .fit_ratio(self.original_ratio)
            .to_size(round_for_ratio=True)
        )

        # Using nice, round integers for gaps, to avoid some weird irregular
        # gaps here and there:
        self.row_gap = int(outfile_size.height / self.size_chars.height)
        self.column_gap = int(outfile_size.width / self.size_chars.width)

        # Then we have to adjust the output size a little:
        outfile_size.width = self.column_gap * self.size_chars_rounded.width
        outfile_size.height = self.row_gap * self.size_chars_rounded.height

        self.font = ImageFont.truetype(str(self.font_path), size=self.row_gap * 0.75)
        self.image = Image.new(
            mode="RGBA",
            size=outfile_size.tuple,
            color=self.background.rgba_tuple if self.background else 0,
        )
        self.draw = ImageDraw.Draw(self.image)
