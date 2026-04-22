from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, ClassVar

from pydantic_settings import BaseSettings


if TYPE_CHECKING:
    from image2ascii.image import ImagePlus


class BaseCliSubCommand(BaseSettings, ABC):
    @abstractmethod
    def run(self): ...


class BasePlugin:
    cli_subcommands: ClassVar[dict[str, type[BaseCliSubCommand]]] = {}

    def pre_enhance(self, image: "ImagePlus"): ...

    def post_enhance(self, image: "ImagePlus"): ...
