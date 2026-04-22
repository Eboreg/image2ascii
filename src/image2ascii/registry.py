from importlib.metadata import entry_points
from typing import TYPE_CHECKING, ClassVar

from image2ascii.timing import timer


if TYPE_CHECKING:
    from image2ascii.image import ImagePlus
    from image2ascii.plugin import BaseCliSubCommand, BasePlugin


class Registry:
    __plugin_classes: list[type["BasePlugin"]] | None = None
    __singleton: ClassVar["Registry | None"] = None

    plugins: list["BasePlugin"]

    @timer
    def __init__(self):
        self.plugins = []
        for plugin_class in self.get_plugin_classes():
            self.plugins.append(plugin_class())

    def get_cli_subcommands(self):
        subcommands: dict[str, type["BaseCliSubCommand"]] = {}

        for plugin in self.plugins:
            subcommands.update(plugin.cli_subcommands)

        return subcommands

    @timer
    def get_plugin_classes(self) -> list[type["BasePlugin"]]:
        if self.__plugin_classes is None:
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

            self.__plugin_classes = plugin_classes

        return self.__plugin_classes

    @timer
    def post_enhance(self, image: "ImagePlus"):
        for plugin in self.plugins:
            plugin.post_enhance(image)

    @timer
    def pre_enhance(self, image: "ImagePlus"):
        for plugin in self.plugins:
            plugin.pre_enhance(image)

    @classmethod
    def singleton(cls) -> "Registry":
        if cls.__singleton is None:
            cls.__singleton = cls()
        return cls.__singleton
