from textual.app import App

from image2ascii_tui.main_screen import MainScreen


class Image2AsciiApp(App):
    MODES = {
        "main": MainScreen,
    }
    DEFAULT_MODE = "main"
