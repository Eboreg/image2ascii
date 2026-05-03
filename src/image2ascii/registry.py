from importlib.metadata import entry_points
from typing import TYPE_CHECKING, ClassVar

from typing_extensions import Self

from image2ascii.timing import timer


if TYPE_CHECKING:
    from image2ascii.image import ImagePlus
    from image2ascii.plugin import BasePlugin


class Registry:
    __singleton: ClassVar[Self | None] = None

    plugins: list["BasePlugin"]

    def __new__(cls) -> Self:
        if cls.__singleton is None:
            cls.__singleton = super().__new__(cls)
            cls.__singleton.plugins = [plugin() for plugin in cls.get_plugin_classes()]
        return cls.__singleton

    def get_cli_subcommands(self):
        return {k: v for plugin in self.plugins for k, v in plugin.cli_subcommands.items()}

    def get_completers(self):
        return {k: v for plugin in self.plugins for k, v in plugin.completers.items()}

    @staticmethod
    def get_plugin_classes() -> list[type["BasePlugin"]]:
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

        return plugin_classes

    @timer
    def post_enhance(self, image: "ImagePlus"):
        for plugin in self.plugins:
            plugin.post_enhance(image)

    @timer
    def pre_enhance(self, image: "ImagePlus"):
        for plugin in self.plugins:
            plugin.pre_enhance(image)
