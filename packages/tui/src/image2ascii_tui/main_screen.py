from pathlib import Path

from textual.containers import Horizontal
from textual.reactive import var
from textual.screen import Screen
from textual.widgets import DirectoryTree, Footer

from image2ascii_tui.file_browser_tree import FileBrowserTree
from image2ascii_tui.image_view import ImageView


class MainScreen(Screen):
    CSS = """
    FileBrowserTree {
        width: 50;
    }
    """

    image_path: var[Path | None] = var(None)

    def compose(self):
        with Horizontal():
            yield FileBrowserTree(Path.home())
            yield ImageView().data_bind(MainScreen.image_path)
        yield Footer()

    def on_directory_tree_file_selected(self, event: DirectoryTree.FileSelected):
        self.log(event, event.node, event.path)
        self.image_path = event.path
