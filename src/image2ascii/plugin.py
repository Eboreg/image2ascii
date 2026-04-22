from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, ClassVar, Generic, TypeVar

from pydantic_settings import BaseSettings


if TYPE_CHECKING:
    from image2ascii.config import Config
    from image2ascii.image import ImagePlus


_Config = TypeVar("_Config", bound="Config")

class BaseCliSubCommand(BaseSettings, ABC):
    @abstractmethod
    def run(self): ...


class BasePlugin(Generic[_Config]):
    cli_subcommands: ClassVar[dict[str, type[BaseCliSubCommand]]] = {}
    config_class: ClassVar[type["Config"] | None] = None

    def __init__(self, config: _Config): ...

    def start(self, config: _Config): ...

    def pre_enhance(self, image: "ImagePlus"): ...

    def post_enhance(self, image: "ImagePlus"): ...
