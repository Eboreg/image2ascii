# image2ascii

Converts images to ASCII, with a twist; it traces edges in the image and attempts to render them with suitably formed characters, à la good old handmade ASCII art:

![FECbm3SXoAM-EnY](https://user-images.githubusercontent.com/1786886/141609990-7e2c0471-2b13-45ff-bff8-c6fd2489c9fe.png)

It can also crop, output ANSI colour, adjust contrast/colour balance/brightness, invert, and other nice stuff, as well as output to HTML.

## Installation

```shell
# You do use virtual envs, right?
python3 -m venv .venv
source .venv/bin/activate
./setup.py install
```

## Usage

### CLI

Installation instructions above creates an `image2ascii` command, run it for more info. Play around with various combinations of `--invert`, `--invert-colors`, and `--swap-bw`, until the results are to your liking.

### HTML

This is the simplest possible way to render HTML:

```python
from image2ascii.core import Image2ASCII
from image2ascii.output import HTMLFormatter

print(Image2ASCII("image.png").prepare().render(formatter=HTMLFormatter()))
```

But you are a highly cultured individual who shouldn't settle for that baseline. Check out the `Image2ASCII` class for more options, and remember to always run `prepare()` before the final `render()`.

## Everything you never wanted to know but somehow are reading right now anyway

This project is totally in alpha and makes no guarantees for anything whatsoever.

Uses:
* [Pillow](https://python-pillow.org/)
* [Matplotlib](https://matplotlib.org/)
* [Colorama](https://github.com/tartley/colorama)
