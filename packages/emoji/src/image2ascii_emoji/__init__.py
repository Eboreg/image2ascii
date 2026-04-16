from PIL.Image import Image
from image2ascii.config import Config as BaseConfig
from image2ascii.plugin import BasePlugin
from image2ascii.types import ImageArray


__all__ = ["Config", "Plugin"]


class Config(BaseConfig):
    apa: str = "hora"


class Plugin(BasePlugin[Config]):
    config_class = Config

    def post_create_matrix(self, image: Image, matrix: ImageArray) -> ImageArray | None:
        return matrix[::-1]
