from importlib.metadata import entry_points
from typing import TYPE_CHECKING, ClassVar, TypeVar

from image2ascii.timing import timer
from image2ascii.types import ImageArray


if TYPE_CHECKING:
    from PIL import Image

    from image2ascii.config import Config
    from image2ascii.plugin import BasePlugin


_Config = TypeVar("_Config", bound="Config")


class Registry:
    __plugin_classes: ClassVar[list[type["BasePlugin"]] | None] = None

    plugins: list["BasePlugin"]

    @classmethod
    @timer
    def extend_config_class(cls, base: type[_Config]):
        result = base
        for plugin_class in cls.get_plugin_classes():
            if plugin_class.config_class is not None and plugin_class.config_class is not base:
                result = base.extend(plugin_class.config_class)
        return result

    @classmethod
    @timer
    def get_plugin_classes(cls) -> list[type["BasePlugin"]]:
        if cls.__plugin_classes is None:
            from image2ascii.plugin import BasePlugin

            plugin_classes: list[type[BasePlugin]] = []

            for entry_point_def in entry_points(group="i2a_plugins"):
                entry_point = entry_point_def.load()
                if isinstance(entry_point, type) and issubclass(entry_point, BasePlugin):
                    plugin_classes.append(entry_point)
                else:
                    for member_name in getattr(entry_point, "__all__", []):
                        member = getattr(entry_point, member_name)
                        if isinstance(member, type) and issubclass(member, BasePlugin):
                            plugin_classes.append(member)

            cls.__plugin_classes = plugin_classes

        return cls.__plugin_classes

    @timer
    def __init__(self, config: "Config"):
        self.plugins = []
        for plugin_class in self.__class__.get_plugin_classes():
            self.plugins.append(plugin_class(config))

    @timer
    def pre_enhance(self, image: "Image.Image") -> "Image.Image":
        for plugin in self.plugins:
            if new_image := plugin.pre_enhance(image):
                image = new_image

        return image

    @timer
    def post_enhance(self, image: "Image.Image") -> "Image.Image":
        for plugin in self.plugins:
            if new_image := plugin.post_enhance(image):
                image = new_image

        return image

    @timer
    def pre_create_matrix(self, image: "Image.Image", matrix: ImageArray) -> ImageArray:
        for plugin in self.plugins:
            new_matrix = plugin.pre_create_matrix(image, matrix)
            if new_matrix is not None:
                matrix = new_matrix

        return matrix

    @timer
    def post_create_matrix(self, image: "Image.Image", matrix: ImageArray) -> ImageArray:
        for plugin in self.plugins:
            new_matrix = plugin.post_create_matrix(image, matrix)
            if new_matrix is not None:
                matrix = new_matrix

        return matrix
