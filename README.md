# image2ascii

Converts images to ASCII, with a twist; it traces edges in the image and attempts to render them with suitably formed characters, à la good old handmade ASCII art:

![Donald Duck](https://user-images.githubusercontent.com/1786886/142641664-5e5450c0-616e-473d-b1bb-43f1cc7a8161.png)

It can also crop, output ANSI colour, adjust contrast/colour balance/brightness, invert, and other nice stuff, as well as render HTML.

## Installation

```shell
# You do use virtual envs, right?
python3 -m venv .venv
source .venv/bin/activate
./setup.py install
```

## Usage

### CLI

Installation per instructions above creates an `image2ascii` command; run it for more info. Play around with various combinations of `--invert`, `--invert-colors`, and `--swap-bw`, until the results are to your liking. `--crop` is also highly recommended.

### HTML

This is the simplest possible way to render HTML:

```python
from image2ascii.core import Image2ASCII

print(Image2ASCII("image.png").set_output_format("html").render())
```

But you are a highly cultured individual who shouldn't settle for that sad and pathetic baseline. Check out the `Image2ASCII` class for more options.

## Everything you never wanted to know but somehow are reading right now anyway

This project is totally in alpha and makes no guarantees for anything whatsoever.

Shouts out to:
* [Pillow](https://python-pillow.org/)
* [Matplotlib](https://matplotlib.org/)
* [Colorama](https://github.com/tartley/colorama)
* [Numpy](https://numpy.org/)
* [Werkzeug](https://werkzeug.palletsprojects.com/)
