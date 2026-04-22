import logging

from PIL import Image
from pydantic import AliasChoices, Field
from pydantic_settings import (
    BaseSettings,
    CliApp,
    CliPositionalArg,
    CliSubCommand,
    CliToggleFlag,
    SettingsConfigDict,
    get_subcommand,
)

from image2ascii.color import ANSI_COLORS, ANSI_RESET_FG
from image2ascii.config import ColorSettings as BaseColorSettings, Config as BaseConfig
from image2ascii.config_types import NullableColorType
from image2ascii.enums import ColorInferenceMethod
from image2ascii.plugin import BaseCliSubCommand
from image2ascii.renderers import ConsoleRenderer, ImageRenderer
from image2ascii.timing import print_results
from image2ascii.workhorse import Workhorse


logger = logging.getLogger(__name__)


class ZoomSettings(BaseSettings, extra="ignore", validate_assignment=True):
    factor: float = Field(default=1, gt=0)
    x: float = Field(default=0.5, ge=0, le=1, description="Relative X position to zoom in on")
    y: float = Field(default=0.5, ge=0, le=1, description="Relative Y position to zoom in on")


class ColorSettings(BaseColorSettings):
    border: NullableColorType = None


class CliConvertSettings(BaseConfig, validate_assignment=True):
    zoom: ZoomSettings = Field(default_factory=ZoomSettings)
    color: ColorSettings = Field(default_factory=ColorSettings) # pyright: ignore[reportIncompatibleVariableOverride]
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
            "Only valid for console output. Adds a this amount of blank spaces to the top and bottom of the output, "
            "and the double amount to the left and right."
        ),
    )
    border: bool = Field(
        default=False,
        description="Only valid for console output. Adds a nice border.",
    )
    border_color: NullableColorType = None
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
    filename: CliPositionalArg[str]

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

        if self.filename.lower().endswith(".svg"):
            horse = Workhorse.load_svg(self.filename, self)
        else:
            horse = Workhorse.load(self.filename, self)

        if self.outfile:
            renderer = ImageRenderer(self.outfile_size)
            renderer.image.save(self.outfile)
            logger.info(f"Wrote {self.outfile}.")
        else:
            renderer = ConsoleRenderer(
                margins=self.margins,
                border=self.border,
                border_color=self.color.border or self.color.default,
            )
            horse.prepare_and_render(renderer)

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


class Cli(
    BaseSettings,
    cli_avoid_json=True,
    cli_enforce_required=True,
    cli_hide_none_type=True,
    cli_ignore_unknown_args=True,
    cli_implicit_flags="dual",
    cli_kebab_case="all",
    cli_parse_args=True,
    cli_parse_none_str="none",
    cli_prog_name="i2a",
    use_enum_values=True,
):
    conv: CliSubCommand[CliFileConvertSettings] = Field(description="Convert a file")
    colors: CliSubCommand[ColorGuide] = Field(description="A little colour guide")

    model_config = SettingsConfigDict(
        cli_shortcuts={
            "viewport.columns": ["cols", "c"],
            "viewport.rows": ["rows", "r"],
            "color.background": ["background", "bg"],
            "zoom.factor": "z",
            "effect.brightness": "brightness",
            "effect.color-balance": "color-balance",
            "effect.contrast": "contrast",
            "effect.invert": "invert",
            "effect.sharpness": "sharpness",
        },
    )

    def cli_cmd(self):
        if cmd := self.get_subcommand():
            cmd.run()
        else:
            CliApp.print_help(self)

    def get_subcommand(self) -> BaseCliSubCommand | None:
        if cmd := get_subcommand(self, is_required=False):
            if isinstance(cmd, BaseCliSubCommand):
                return cmd
