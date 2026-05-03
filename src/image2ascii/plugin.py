from abc import ABC, abstractmethod
from collections.abc import Callable, Sequence
from typing import TYPE_CHECKING, Any, ClassVar

from pydantic.fields import FieldInfo
from pydantic_settings import BaseSettings


if TYPE_CHECKING:
    from image2ascii.image import ImagePlus


class BaseCliSubCommand(BaseSettings, ABC):
    @abstractmethod
    def run(self): ...


class BasePlugin:
    cli_subcommands: ClassVar[dict[str, type[BaseCliSubCommand] | tuple[type[BaseCliSubCommand], FieldInfo]]] = {}
    completers: ClassVar[dict[str, Callable[[Any], Sequence[str]]]] = {}

    def pre_enhance(self, image: "ImagePlus"): ...

    def post_enhance(self, image: "ImagePlus"): ...
