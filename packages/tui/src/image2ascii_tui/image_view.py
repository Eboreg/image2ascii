import dataclasses
from pathlib import Path

from textual import on, work
from textual.content import Content
from textual.events import Resize
from textual.message import Message
from textual.reactive import var
from textual.widget import Widget
from textual.widgets import LoadingIndicator, Static

from image2ascii.color_converters import SimpleRGBColorConverter
from image2ascii.config import Config
from image2ascii.geometry import PointF, Size, SolidShapes
from image2ascii.workhorse import Workhorse
from image2ascii_tui.renderer import TextualRenderer


@dataclasses.dataclass
class ZoomAndCenter:
    zoom: float = 1
    center: PointF = dataclasses.field(default_factory=lambda: PointF(0.5, 0.5))


class ImageView(Widget, can_focus=True):
    BINDINGS = [
        ("+", "zoom_in", "Zoom in"),
        ("-", "zoom_out", "Zoom out"),
        ("up", "pan(0, -1)", "Pan up"),
        ("down", "pan(0, 1)", "Pan down"),
        ("left", "pan(-1, 0)", "Pan left"),
        ("right", "pan(1, 0)", "Pan right"),
    ]
    DEFAULT_CSS = """
    ImageView {
        # border: round red;
        # width: 100%;
        # height: 100%;
        # width: 80;
        # height: 40;
        max-width: 80;
        max-height: 40;
        align: center middle;
        layers: base overlay;

        &.loading {
            #image {
                opacity: 50%;
            }
            #loading {
                display: block;
            }
        }

        #image {
            layer: base;
            # width: auto;
        }
        #loading {
            height: 1;
            width: auto;
            layer: overlay;
            display: none;
        }
    }
    """

    @dataclasses.dataclass
    class Rendered(Message):
        content: Content
        size: Size

    image_path: var[Path | None] = var(None)
    is_loading: var[bool] = var(False, toggle_class="loading")
    zoom_and_center: var[ZoomAndCenter] = var(ZoomAndCenter(), init=False)
    horse: Workhorse | None = None

    def __init__(self):
        super().__init__()
        self.config = Config(shapeset=SolidShapes)
        # self.config = Config()
        self.config.transparency.disable = True
        self.config.crop = False
        self.config.quality = 1
        self.config.color.converter_type = SimpleRGBColorConverter
        self.image_element = Static(id="image")
        if self.config.color.background:
            self.styles.background = self.config.color.background.css

    def action_pan(self, x: int, y: int):
        if self.horse:
            steps = self.horse.get_pan_steps(self.zoom_and_center.zoom, viewport_step=0.5)
            self.update_zoom_and_center(center_delta=steps * PointF(x, y))

    def update_zoom_and_center(self, zoom_delta: float = 0, center_delta: PointF | None = None):
        if self.horse:
            zoom = max(1, self.zoom_and_center.zoom + zoom_delta)
            if center_delta:
                center = self.zoom_and_center.center + center_delta
            else:
                center = self.zoom_and_center.center
            constraints = self.horse.get_center_constraints(zoom)
            zoom_and_center = ZoomAndCenter(zoom=zoom, center=center.coerce_between(*constraints))
            if zoom_and_center != self.zoom_and_center:
                self.zoom_and_center = zoom_and_center
                self.is_loading = True
                self.render_image(self.horse)

    def action_zoom_in(self):
        self.update_zoom_and_center(zoom_delta=1)

    def action_zoom_out(self):
        self.update_zoom_and_center(zoom_delta=-1)

    def compose(self):
        yield self.image_element
        yield LoadingIndicator(id="loading")

    @on(Rendered)
    async def on_rendered(self, event: Rendered):
        self.image_element.update(event.content)
        self.is_loading = False

    def on_resize(self, event: Resize):
        self.config.viewport.columns = event.size.width
        self.config.viewport.rows = event.size.height
        if self.horse:
            self.is_loading = True
            self.render_image(self.horse)

    @work(thread=True, exclusive=True)
    def render_image(self, horse: Workhorse):
        renderer = TextualRenderer()
        horse.zoom(self.zoom_and_center.zoom, self.zoom_and_center.center)
        horse.render(renderer)
        renderer.render(horse.generate_output())
        horse.zoom_and_render(renderer, self.zoom_and_center.zoom, self.zoom_and_center.center)
        content = renderer.render_content()
        self.log(
            "render_image:",
            "self.zoom_and_center:",
            self.zoom_and_center,
            "horse.final_size_chars:",
            horse.final_size_chars,
            "horse.final_size_px:",
            horse.final_size_px,
            "config.viewport_size_px:",
            self.config.viewport_size_px,
            "horse.image.size:",
            horse.image.size,
            "renderer.size_chars:",
            renderer.size_chars,
        )
        self.post_message(ImageView.Rendered(content=content, size=renderer.size_chars))

    def watch_image_path(self, value: Path | None):
        if value is not None:
            self.horse = Workhorse.load_file(value, self.config)
            self.zoom_and_center = ZoomAndCenter()
            self.is_loading = True
            self.render_image(self.horse)
