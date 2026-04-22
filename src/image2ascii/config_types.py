import importlib
from typing import Annotated, Any

import numpy as np
from PIL.Image import Resampling
from pydantic import BeforeValidator, PlainSerializer

from image2ascii.color import AnsiColor, Color
from image2ascii.color_converters import (
    AbstractColorConverter,
    AnsiColorConverter,
    FullRGBColorConverter,
    GrayScaleColorConverter,
    NullColorConverter,
)
from image2ascii.enums import ColorInferenceMethod
from image2ascii.geometry import DefaultShapes, ShapeSet, SolidShapes


def import_path(path: str):
    if "." not in path:
        path = f"image2ascii.{path}"
    module_name, member_name = path.rsplit(".", maxsplit=1)
    module = importlib.import_module(module_name)
    if not hasattr(module, member_name):
        raise AttributeError(f"'{member_name}' not found in '{module_name}'")
    return getattr(module, member_name)


def serialize_color(value: Color | None) -> str | None:
    if isinstance(value, AnsiColor):
        return value.name
    if isinstance(value, Color):
        return value.css
    return None


def serialize_color_converter(value: type[AbstractColorConverter]):
    if hasattr(value, "SHORTHAND"):
        return value.SHORTHAND
    return serialize_importable(value)


def serialize_importable(value: type) -> str:
    return value.__module__ + "." + value.__name__


def serialize_resample(value: int) -> str:
    return Resampling(value).name


def serialize_shapeset(value: type[ShapeSet]):
    if hasattr(value, "SHORTHAND"):
        return value.SHORTHAND
    return serialize_importable(value)


def validate_color(value: Any) -> Color | None:
    if isinstance(value, Color) or value is None:
        return value
    if isinstance(value, str):
        return Color.parse_string(value)
    if isinstance(value, list):
        return Color(np.array(value, dtype=np.uint8))
    return value


def validate_color_converter(value: Any) -> type[AbstractColorConverter]:
    if isinstance(value, type) and issubclass(value, AbstractColorConverter):
        return value

    if isinstance(value, str):
        for klass in (NullColorConverter, GrayScaleColorConverter, AnsiColorConverter, FullRGBColorConverter):
            if klass.SHORTHAND == value:
                return klass

        try:
            klass = import_path(value)
            assert issubclass(klass, AbstractColorConverter)
            return klass
        except Exception as e:
            raise ValueError(e) from e

    raise ValueError(f"Expected a color converter class, found {value}")


def validate_resample(value: str | Resampling) -> Resampling:
    if isinstance(value, Resampling):
        return value
    value = value.upper()
    if value in Resampling.__members__:
        return Resampling[value]
    if value in Resampling:
        return Resampling(value)
    raise ValueError


def validate_shapeset(value: Any) -> type[ShapeSet]:
    if isinstance(value, type) and issubclass(value, ShapeSet):
        return value

    if isinstance(value, str):
        for klass in (DefaultShapes, SolidShapes):
            if klass.SHORTHAND == value:
                return klass

        try:
            klass = import_path(value)
            assert issubclass(klass, ShapeSet)
            return klass
        except Exception as e:
            raise ValueError(e) from e
    raise ValueError(f"Expected a ShapeSet class, found {value}")


ColorConverterType = Annotated[
    type[AbstractColorConverter],
    BeforeValidator(validate_color_converter),
    PlainSerializer(serialize_color_converter, return_type=str),
]

ColorInferenceMethodType = Annotated[ColorInferenceMethod, BeforeValidator(ColorInferenceMethod.validate)]

NullableColorType = Annotated[
    Color | None,
    PlainSerializer(serialize_color, return_type=str),
    BeforeValidator(validate_color),
]

ResampleType = Annotated[
    Resampling,
    PlainSerializer(serialize_resample, return_type=str),
    BeforeValidator(validate_resample),
]

ShapeSetType = Annotated[
    type[ShapeSet],
    BeforeValidator(validate_shapeset),
    PlainSerializer(serialize_shapeset, return_type=str),
]
