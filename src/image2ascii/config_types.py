import importlib
from collections.abc import Sequence
from typing import Annotated, Any

import numpy as np
from PIL.Image import Resampling
from pydantic import BeforeValidator, PlainSerializer
from pydantic_settings import NoDecode

from image2ascii.color import AnsiColor, Color
from image2ascii.color_converters import AbstractColorConverter, concrete_converter_classes
from image2ascii.enums import ColorInferenceMethod
from image2ascii.geometry import DefaultShapes, Point, PointF, ShapeSet, SolidShapes


def import_path(path: str):
    if "." not in path:
        path = f"image2ascii.{path}"
    module_name, member_name = path.rsplit(".", maxsplit=1)
    module = importlib.import_module(module_name)
    if not hasattr(module, member_name):
        raise AttributeError(f"'{member_name}' not found in '{module_name}'")
    return getattr(module, member_name)


def serialize_color(value: Color) -> str:
    if isinstance(value, AnsiColor):
        return value.name
    return value.css_rgba


def serialize_color_nullable(value: Color | None) -> str | None:
    if isinstance(value, AnsiColor):
        return value.name
    if isinstance(value, Color):
        return value.css_rgba
    return None


def serialize_color_converter(value: type[AbstractColorConverter]):
    if hasattr(value, "SHORTHAND"):
        return value.SHORTHAND
    return serialize_importable(value)


def serialize_importable(value: type) -> str:
    return value.__module__ + "." + value.__name__


def serialize_point_f_nullable(value: PointF | None) -> str | None:
    if value is not None:
        return f"{value.x},{value.y}"
    return None


def serialize_point_f(value: PointF) -> str:
    return f"{value.x},{value.y}"


def serialize_resample(value: int) -> str:
    return Resampling(value).name


def serialize_shapeset(value: type[ShapeSet]):
    if hasattr(value, "SHORTHAND"):
        return value.SHORTHAND
    return serialize_importable(value)


def validate_color(value: Any) -> Color:
    if isinstance(value, Color):
        return value
    if isinstance(value, str):
        color = Color.parse_string(value)
        if color is None:
            raise ValueError(value)
        return color
    if isinstance(value, list):
        return Color(np.array(value, dtype=np.uint8))
    raise ValueError(value)


def validate_color_nullable(value: Any) -> Color | None:
    if isinstance(value, Color) or value is None:
        return value
    if isinstance(value, str):
        return Color.parse_string(value)
    if isinstance(value, list):
        return Color(np.array(value, dtype=np.uint8))
    return None


def validate_color_converter(value: Any) -> type[AbstractColorConverter]:
    if isinstance(value, type) and issubclass(value, AbstractColorConverter):
        return value

    if isinstance(value, str):
        for klass in concrete_converter_classes():
            if klass.SHORTHAND == value:
                return klass

        try:
            klass = import_path(value)
            assert issubclass(klass, AbstractColorConverter)
            return klass
        except Exception as e:
            raise ValueError(e) from e

    raise ValueError(f"Expected a color converter class, found {value}")


def validate_point_f(value: Any) -> PointF:
    if isinstance(value, PointF):
        return value
    if isinstance(value, Point):
        return value.to_point_f()
    if isinstance(value, str):
        value = value.split(",")
    if isinstance(value, Sequence):
        if len(value) == 1:
            x, y = float(value[0]), float(value[0])
        else:
            x, y = [float(v) for v in value[:2]]
        return PointF(x, y)
    raise ValueError(f"Could not convert '{value}' to PointF")


def validate_point_f_nullable(value: Any) -> PointF | None:
    if isinstance(value, PointF) or value is None:
        return value
    if isinstance(value, Point):
        return value.to_point_f()
    if isinstance(value, str):
        value = value.split(",")
    if isinstance(value, Sequence):
        x, y = [float(v) for v in value]
        return PointF(x, y)
    return None


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

ColorType = Annotated[
    Color,
    PlainSerializer(serialize_color, return_type=str),
    BeforeValidator(validate_color),
]

NullableColorType = Annotated[
    Color | None,
    PlainSerializer(serialize_color_nullable, return_type=str | None),
    BeforeValidator(validate_color_nullable),
]

NullablePointFType = Annotated[
    PointF | None,
    PlainSerializer(serialize_point_f_nullable, return_type=str | None),
    BeforeValidator(validate_point_f_nullable),
]

"""
Because PointF is a dataclass, Pydantic decides that it's a "complex type" and
tries to run json.loads() on the input value for some reason, which fails if
the input value is a string like '0.5, 0.7'. Annotating with NoDecode is a way
around this, albeit probably not the "correct" one. Leaving it until I learn
how to handle this more better.
"""
PointFType = Annotated[
    PointF,
    PlainSerializer(serialize_point_f, return_type=str),
    BeforeValidator(validate_point_f),
    NoDecode,
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
