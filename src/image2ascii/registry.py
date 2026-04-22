from importlib.metadata import entry_points
from typing import TYPE_CHECKING, ClassVar, TypeVar

from image2ascii.timing import timer


if TYPE_CHECKING:
    from image2ascii.config import Config
    from image2ascii.image import ImagePlus
    from image2ascii.plugin import BaseCliSubCommand, BasePlugin


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
    def get_cli_subcommands(cls):
        subcommands: dict[str, type["BaseCliSubCommand"]] = {}

        for plugin_class in cls.get_plugin_classes():
            subcommands.update(plugin_class.cli_subcommands)

        return subcommands

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
    def pre_enhance(self, image: "ImagePlus"):
        for plugin in self.plugins:
            plugin.pre_enhance(image)

    @timer
    def post_enhance(self, image: "ImagePlus"):
        for plugin in self.plugins:
            plugin.post_enhance(image)
