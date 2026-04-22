import enum
from typing import Annotated, Any, Self

from pydantic import BeforeValidator


class Gender(enum.StrEnum):
    FEMALE = "female"
    MALE = "male"

    @staticmethod
    def validate_gender(value: str) -> "Gender | None":
        value = value.upper()
        if value in Gender.__members__:
            return Gender[value]
        if value in Gender:
            return Gender(value)
        return None


class SkinTone(enum.StrEnum):
    LIGHT = "light"
    MEDIUM_LIGHT = "medium-light"
    MEDIUM = "medium"
    MEDIUM_DARK = "medium-dark"
    DARK = "dark"

    @classmethod
    def get(cls, v: Any) -> Self | None:
        if v in cls:
            return cls(v)
        return None

    @staticmethod
    def validate_skin_tone(value: str) -> "SkinTone | None":
        value = value.upper().replace("-", "_")
        if value in SkinTone.__members__:
            return SkinTone[value]
        if value in SkinTone:
            return SkinTone(value)
        return None


GenderType = Annotated[Gender, BeforeValidator(Gender.validate_gender)]

SkinToneType = Annotated[SkinTone, BeforeValidator(SkinTone.validate_skin_tone)]
