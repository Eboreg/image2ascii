import logging

from PIL import Image
from pydantic import Field
from pydantic_settings import CliPositionalArg, CliToggleFlag, SettingsConfigDict

from image2ascii.config import Config as BaseConfig
from image2ascii.config_types import NullableColorType
from image2ascii.enums import ColorInferenceMethod
from image2ascii.renderers import ConsoleRenderer, ImageRenderer
from image2ascii.timing import print_results
from image2ascii.workhorse import Workhorse


logger = logging.getLogger(__name__)


class Config(
    BaseConfig,
    cli_parse_args=True,
    cli_implicit_flags="dual",
    cli_kebab_case=True,
    cli_ignore_unknown_args=True,
    cli_avoid_json=True,
    cli_enforce_required=True,
    cli_prog_name="i2a",
    cli_parse_none_str="none",
):
    filename: CliPositionalArg[str]
    outfile: str | None = Field(description="Image file to write the results to", default=None)
    outfile_size: int = Field(
        default=1000,
        description="Width or height (whichever one is largest) of the file produced by '--outfile'",
    )
    zoom: float = Field(default=1, gt=0)
    x: float = Field(default=0.5, ge=0, le=1, description="Relative X position to zoom in on")
    y: float = Field(default=0.5, ge=0, le=1, description="Relative Y position to zoom in on")
    best: CliToggleFlag[bool] = Field(
        default=False,
        description=(
            "Shorthand for '--quality 10 --color-inference-method MOST_COMMON --max-original-size None "
            "--min-likeness 1'"
        ),
    )
    fastest: CliToggleFlag[bool] = Field(
        default=False,
        description=(
            "Shorthand for '--quality 1 --trans.disable --resample-method NEAREST --color-inference-method MEDIAN'"
        ),
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
    debug: bool = False

    model_config = SettingsConfigDict(
        cli_shortcuts={
            "viewport-columns": ["cols", "c"],
            "viewport-rows": ["rows", "r"],
            "outfile": "o",
            "background": "bg",
        },
    )

    def cli_cmd(self):
        if self.debug:
            from image2ascii import timing
            timing.TIMING_ENABLED = True

        if self.fastest:
            self.transparency.disable = True
            self.quality = 1
            self.resample_method = Image.Resampling.NEAREST
            self.color_inference_method = ColorInferenceMethod.MEDIAN
        elif self.best:
            self.quality = 10
            self.color_inference_method = ColorInferenceMethod.MOST_COMMON
            self.max_original_size = None
            self.min_likeness = 1.0

        if self.filename.lower().endswith(".svg"):
            horse = Workhorse.load_svg(self.filename, self)
            # ascii = AsciiImage.load_svg(self.filename, self)
        else:
            horse = Workhorse.load(self.filename, self)
            # ascii = AsciiImage.load(self.filename, self)

        if self.outfile:
            renderer = ImageRenderer(self.outfile_size)
            # ascii.prepare_and_render(renderer, zoom=self.zoom, center=(self.x, self.y))
            renderer.image.save(self.outfile)
            logger.info(f"Wrote {self.outfile}.")
        else:
            renderer = ConsoleRenderer(
                margins=self.margins,
                border=self.border,
                border_color=self.border_color or self.default_color,
            )
            horse.prepare_and_render(renderer)
            # horse.zoom(4.0)
            # ascii.prepare_and_render(renderer, zoom=self.zoom, center=(self.x, self.y))
            print()

        if self.debug:
            print_results()
