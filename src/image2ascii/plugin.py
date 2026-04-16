from typing import TYPE_CHECKING, Generic, TypeVar

from PIL import Image

from image2ascii.types import ImageArray


if TYPE_CHECKING:
    from image2ascii.config import Config


_Config = TypeVar("_Config", bound="Config")


class BasePlugin(Generic[_Config]):
    config_class: type["Config"] | None = None

    def __init__(self, config: _Config):
        ...

    def start(self, config: _Config):
        ...

    def pre_enhance(self, image: Image.Image) -> Image.Image | None:
        return None

    def post_enhance(self, image: Image.Image) -> Image.Image | None:
        return None

    def pre_create_matrix(self, image: Image.Image, matrix: ImageArray) -> ImageArray | None:
        return None

    def post_create_matrix(self, image: Image.Image, matrix: ImageArray) -> ImageArray | None:
        return None
