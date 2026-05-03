from pathlib import Path
from typing import Iterable

from PIL.Image import _EXTENSION_PLUGIN
from textual.reactive import var
from textual.widgets import DirectoryTree


class FileBrowserTree(DirectoryTree):
    BINDINGS = [
        ("left", "left"),
        ("right", "right"),
        ("ctrl+left", "scroll_left"),
        ("ctrl+right", "scroll_right"),
        ("h", "show_hidden", "Show hidden files"),
        ("h", "hide_hidden", "Hide hidden files"),
    ]
    ICON_FILE = "🖼️ "
    SUFFIXES = _EXTENSION_PLUGIN.keys()

    show_hidden: var[bool] = var(False, bindings=True)

    def action_hide_hidden(self):
        self.__toggle_show_hidden()

    async def action_left(self):
        if self.cursor_node and self.cursor_node.allow_expand and self.cursor_node.is_expanded:
            self.cursor_node.collapse()
        else:
            await self.run_action("cursor_up")

    async def action_right(self):
        if self.cursor_node and self.cursor_node.allow_expand and self.cursor_node.is_collapsed:
            self.cursor_node.expand()
        else:
            await self.run_action("cursor_down")

    def action_show_hidden(self):
        self.__toggle_show_hidden()

    def check_action(self, action: str, parameters: tuple[object, ...]) -> bool | None:
        if action == "show_hidden":
            return not self.show_hidden
        if action == "hide_hidden":
            return self.show_hidden
        return super().check_action(action, parameters)

    def filter_paths(self, paths: Iterable[Path]) -> Iterable[Path]:
        return (
            path
            for path in paths
            if (self.show_hidden or not path.name.startswith("."))
            and (path.is_dir() or (path.is_file() and path.suffix.lower() in self.SUFFIXES))
        )

    def __toggle_show_hidden(self):
        self.show_hidden = not self.show_hidden
        self.reload()
