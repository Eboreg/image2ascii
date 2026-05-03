from image2ascii.plugin import BaseCliSubCommand
from image2ascii_tui.app import Image2AsciiApp


class TextualSubCommand(BaseCliSubCommand):
    def run(self):
        app = Image2AsciiApp()
        app.run()
