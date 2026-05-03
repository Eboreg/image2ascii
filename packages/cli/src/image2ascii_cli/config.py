from PIL import Image
from pydantic import AliasChoices, Field
from pydantic_settings import BaseSettings, CliPositionalArg, CliToggleFlag

from image2ascii.color import ANSI_COLORS, ANSI_RESET_FG
from image2ascii.config import ColorSettings as BaseColorSettings, Config as BaseConfig
from image2ascii.config_types import NullableColorType, PointFType
from image2ascii.enums import ColorInferenceMethod
from image2ascii.geometry import PointF
from image2ascii.logging import get_logger
from image2ascii.plugin import BaseCliSubCommand
from image2ascii.renderers import ConsoleRenderer, ImageRenderer
from image2ascii.timing import print_results
from image2ascii.workhorse import Workhorse


logger = get_logger(__name__)


class ZoomSettings(BaseSettings, extra="ignore", validate_assignment=True):
    factor: float = Field(default=1, gt=0)
    center: PointFType = Field(default=PointF(0.5, 0.5))


class ColorSettings(BaseColorSettings):
    # TODO: enable border for all renderers (maybe)
    border: NullableColorType = None


class CliConvertSettings(BaseConfig, validate_assignment=True):
    zoom: ZoomSettings = Field(default_factory=ZoomSettings)
    color: ColorSettings = Field(default_factory=ColorSettings)  # pyright: ignore[reportIncompatibleVariableOverride]
    best: CliToggleFlag[bool] = Field(
        default=False,
        description="Shorthand for '--quality 10 --color.inference MOST-COMMON --min-likeness 1'",
    )
    fastest: CliToggleFlag[bool] = Field(
        default=False,
        description="Shorthand for '--quality 1 --trans.disable --resample NEAREST --color.inference MEDIAN'",
    )
    margins: int = Field(
        default=0,
        description=(
            "Only valid for console output. Adds this amount of blank spaces to the left and right of the output, "
            "and half this amount (rounded) to the left and right"
        ),
    )
    border: bool = Field(
        default=False,
        description="Only valid for console output. Adds a nice border",
    )
    outfile: str | None = Field(
        description="Image file to write the results to",
        default=None,
        validation_alias=AliasChoices("o", "outfile"),
    )
    outfile_size: int = Field(
        default=1000,
        description="Width or height (whichever one is largest) of the file produced by '--outfile'",
    )


class CliFileConvertSettings(CliConvertSettings, BaseCliSubCommand, extra="ignore", validate_assignment=True):
    """Convert a file"""

    path: CliPositionalArg[str] = Field(
        description="File to convert; local paths and http(s) paths are both accepted"
    )

    def run(self):
        if self.debug:
            from image2ascii import timing

            timing.TIMING_ENABLED = True

        if self.fastest:
            self.transparency.disable = True
            self.quality = 1
            self.resample = Image.Resampling.NEAREST
            self.color.inference = ColorInferenceMethod.MEDIAN
        elif self.best:
            self.quality = 10
            self.color.inference = ColorInferenceMethod.MOST_COMMON
            self.min_likeness = 1.0

        with Workhorse.load_file(self.path, self) as horse:
            if self.outfile:
                renderer = ImageRenderer(self.outfile_size)
            else:
                renderer = ConsoleRenderer(
                    margins=self.margins,
                    border=self.border,
                    border_color=self.color.border or self.color.default,
                )

            if self.zoom.factor != 1:
                horse.zoom_and_render(renderer, self.zoom.factor, self.zoom.center)
            else:
                horse.prepare_and_render(renderer)

            if self.outfile and isinstance(renderer, ImageRenderer):
                renderer.image.save(self.outfile)
                logger.info(f"Wrote {self.outfile}.")

        if self.debug:
            print_results()


class ColorGuide(BaseCliSubCommand):
    """A little colour guide"""

    def run(self):
        print("When setting colours in the config file or via CLI, you can use the following formats:")
        print()
        print(" * CSS RGB colour strings ('#RRGGBB' or '#RGB', with or without the '#')")
        print(" * 'R,G,B' or '(R, G, B)'")
        print(" * Any of the following ANSI colour constants (case insensitive):")
        print()

        standard_ansi = [c for c in ANSI_COLORS if c.code < 90]
        bright_ansi = [c for c in ANSI_COLORS if c.code >= 90]

        for standard, bright in zip(standard_ansi, bright_ansi, strict=False):
            print(f"  {standard.ansi}██{ANSI_RESET_FG} {standard.name:20s}", end="")
            print(f"{bright.ansi}██{ANSI_RESET_FG} {bright.name}")

        print()
        print("(Yes, I spell it 'colour' in text but 'color' in code. That's just something I do.)")
        print()
