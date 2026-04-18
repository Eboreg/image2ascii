from typing import Literal, Self

import platformdirs
from PIL.Image import Resampling
from pydantic import BaseModel, ConfigDict, Field, create_model
from pydantic_settings import (
    BaseSettings,
    CliToggleFlag,
    PydanticBaseSettingsSource,
    SettingsConfigDict,
    YamlConfigSettingsSource,
)

from image2ascii.color import ANSI_COLOR_DICT
from image2ascii.color_converters import FullRGBColorConverter
from image2ascii.config_types import (
    ColorConverterType,
    NullableColorType,
    ResampleType,
    ShapeSetType,
)
from image2ascii.enums import ColorInferenceMethod
from image2ascii.geometry import DefaultShapes, Size, SizeF


DEFAULT_CHAR_RATIO = 0.469
DEFAULT_MAX_ORIGINAL_SIZE = 2000
DEFAULT_MIN_LIKENESS = 0.9
DEFAULT_MIN_VISIBLE_ALPHA = 0x80
DEFAULT_MIN_VISIBLE_BG_DISTANCE = 150
DEFAULT_MIN_VISIBLE_BRIGHTNESS = 0x30
DEFAULT_QUALITY = 5
DEFAULT_VIEWPORT_COLUMNS = 120
DEFAULT_VIEWPORT_ROWS = 50


def get_app_dirs():
    return platformdirs.PlatformDirs("image2ascii", ensure_exists=True)


class Transparency(BaseModel, validate_assignment=True):
    disable: CliToggleFlag[bool] = Field(default=False, description="Disable all transparency (boring but efficient)")
    methods: list[Literal["bgdistance", "brightness", "alpha"]] = Field(
        default=["bgdistance", "brightness", "alpha"],
        description=(
            "How to detect transparency. 'bgdistance': areas are transparent if they are less than 'min_bg_distance' "
            "different in colour to the background (will only work if there actually is a background colour set). "
            "'brightness': areas are transparent if they are darker than 'min_brightness'. Will normally only be used "
            "if 'bgdistance' is not. 'alpha': areas are transparent if their alpha value is less than 'min_alpha'. "
            "Will be used even if any of the other two are."
        ),
    )
    force_brightness: bool = Field(
        default=False,
        description=(
            "If 'methods' contains both 'bgdistance' and 'brightness', use the 'brightness' method even if a "
            "background colour exists (normally, 'brightness' is skipped in this case)."
        ),
    )
    alpha: int = Field(
        default=DEFAULT_MIN_VISIBLE_ALPHA,
        ge=0,
        le=0xFF,
        description="Pixels with an alpha value lower than this will be treated as transparent (scale: 0-255)",
    )
    bg_distance: int = Field(
        default=DEFAULT_MIN_VISIBLE_BG_DISTANCE,
        ge=0,
        le=765,
        description=(
            "Determine a pixel's transparency by its dissimilarity with the background colour, with this as a lower "
            "threshold (scale: 0-~765)"
        ),
    )
    brightness: int = Field(
        default=DEFAULT_MIN_VISIBLE_BRIGHTNESS,
        ge=0,
        le=0xFF,
        description="Pixels darker than this will be treated as transparent (scale: 0-255)",
    )

    model_config = ConfigDict(extra="ignore")

    def use_bgdistance(self, has_background: bool):
        return not self.disable and "bgdistance" in self.methods and self.bg_distance > 0 and has_background

    def use_brightness(self, has_background: bool):
        return (
            not self.disable and
            (not self.use_bgdistance(has_background) or self.force_brightness) and
            "brightness" in self.methods and
            self.brightness > 0
        )

    def use_alpha(self):
        return not self.disable and "alpha" in self.methods and self.alpha > 0

    def use_nothing(self, has_background: bool):
        return (
            not self.use_bgdistance(has_background) and
            not self.use_brightness(has_background) and
            not self.use_alpha()
        )


class Config(BaseSettings, validate_assignment=True):
    background: NullableColorType = ANSI_COLOR_DICT["BLACK"]
    brightness: float = Field(default=1.0, ge=0, description="0 = completely black image")
    char_ratio: float = Field(
        default=DEFAULT_CHAR_RATIO,
        gt=0,
        description="Width/height ratio of one output character; tweak this if results look squashed or streched out",
    )
    color_balance: float = Field(default=1.0)
    color_converter: ColorConverterType = Field(
        default=FullRGBColorConverter,
        description=(
            "Class responsible for interpreting colours. Built-in choices (with shorthands for convenience): "
            "NullColorConverter ('null'), GrayScaleColorConverter ('grayscale'), AnsiColorConverter ('ansi'), "
            "FullRGBColorConverter ('rgb')"
        ),
    )
    color_inference: ColorInferenceMethod = Field(
        default=ColorInferenceMethod.MEDIAN,
        description=(
            "MEDIAN = pick the median colour for each image section; MOST_COMMON = pick the most frequent one. MEDIAN "
            "seems to be ~10x faster, for what it's worth"
        ),
    )
    contrast: float = Field(default=1.0)
    crop: bool = Field(default=False, description="Remove any empty spaces around the result")
    debug: bool = False
    default_color: NullableColorType = Field(
        default=None,
        description="Fill colour to use when there is no other available."
    )
    invert: bool = Field(default=False, description="Invert all character colours")
    max_original_size: int | None = Field(default=DEFAULT_MAX_ORIGINAL_SIZE, gt=0)
    min_likeness: float = Field(
        default=DEFAULT_MIN_LIKENESS,
        description=(
            "Small performance tweak: For each partly transparent image section, pick the first character that is at "
            "least this similar to it. Set to 1 to always loop through all characters."
        ),
    )
    quality: int = Field(
        default=DEFAULT_QUALITY,
        gt=0,
        description="Higher value = more accurate results but also slower",
    )
    resample: ResampleType = Resampling.NEAREST
    shapeset: ShapeSetType = Field(
        default=DefaultShapes,
        description=(
            "ShapeSet class containing the characters to be used for output. Built-in choices: DefaultShapes "
            "('default'), SolidShapes ('solid')"
        ),
    )
    sharpness: float = Field(default=1.0)
    transparency: Transparency = Field(default_factory=Transparency, alias="trans")
    viewport_columns: int = Field(
        default=DEFAULT_VIEWPORT_COLUMNS,
        gt=0,
        description="Maximum width (in characters) of the output",
    )
    viewport_rows: int = Field(
        default=DEFAULT_VIEWPORT_ROWS,
        gt=0,
        description="Maximum height (in characters) of the output",
    )

    model_config = SettingsConfigDict(yaml_file=get_app_dirs().user_config_path / "config.yaml", extra="ignore")

    @property
    def viewport_size(self) -> Size:
        return Size(self.viewport_columns, self.viewport_rows)

    @property
    def viewport_size_px(self) -> SizeF:
        """
        With 120x40 char viewport, char_ratio=0.4, quality=5: SizeF(600, 500)
        """
        return self.viewport_size * self.quality / SizeF(1, self.char_ratio)

    def merge(self, other: Self) -> Self:
        config_dict = self.model_dump()
        config_dict.update(other.model_dump(exclude_unset=True))

        return self.model_validate(config_dict)

    @classmethod
    def extend(cls, other: type["Config"]):
        default_config = BaseSettings.model_config
        model_config = other.model_config.copy()

        for key, value in cls.model_config.items():
            if key not in default_config or value != default_config[key]:  # type: ignore[ty:invalid-key]
                model_config[key] = value  # type: ignore[ty:invalid-key]

        return create_model(cls.__name__, __base__=(cls, other), __module__=cls.__module__, __config__=model_config)

    @classmethod
    def settings_customise_sources(
        cls,
        settings_cls: type[BaseSettings],
        init_settings: PydanticBaseSettingsSource,
        env_settings: PydanticBaseSettingsSource,
        dotenv_settings: PydanticBaseSettingsSource,
        file_secret_settings: PydanticBaseSettingsSource,
    ) -> tuple[PydanticBaseSettingsSource, ...]:
        return init_settings, YamlConfigSettingsSource(settings_cls)
