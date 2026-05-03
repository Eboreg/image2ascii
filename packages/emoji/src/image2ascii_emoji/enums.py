import enum
from typing import Annotated

from pydantic import BeforeValidator


class Gender(enum.StrEnum):
    FEMALE = "female"
    MALE = "male"

    def __str__(self) -> str:
        return self.name.lower().replace("_", "-")

    @staticmethod
    def validate(value: str | None) -> "Gender | None":
        if value is not None:
            value = value.lower()
            if value in ("female", "woman", "women", "girl", "girls"):
                return Gender.FEMALE
            if value in ("male", "man", "men", "boy", "boys"):
                return Gender.MALE
        return None


class Hair(enum.StrEnum):
    RED = "red"
    CURLY = "curly"
    WHITE = "white"
    BALD = "bald"
    BLOND = "blond"

    def __str__(self) -> str:
        return self.name.lower().replace("_", "-")

    @staticmethod
    def validate(value: str | None) -> "Hair | None":
        if value is not None:
            value = value.upper()
            if value in Hair.__members__:
                return Hair[value]
        return None


class SkinTone(enum.StrEnum):
    LIGHT = "light"
    MEDIUM_LIGHT = "medium-light"
    MEDIUM = "medium"
    MEDIUM_DARK = "medium-dark"
    DARK = "dark"

    def __str__(self) -> str:
        return self.name.lower().replace("_", "-")

    @staticmethod
    def validate(value: str | None) -> "SkinTone | None":
        if value is not None:
            value = value.upper().replace("-", "_")
            if value in SkinTone.__members__:
                return SkinTone[value]
        return None


GenderType = Annotated[Gender, BeforeValidator(Gender.validate)]

HairType = Annotated[Hair, BeforeValidator(Hair.validate)]

SkinToneType = Annotated[SkinTone, BeforeValidator(SkinTone.validate)]
