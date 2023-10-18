# Image2ASCII

Converts images to ASCII, with a twist; it traces edges in the image and attempts to render them with suitably formed characters, à la good old handmade ASCII art:

![Donald Duck](https://user-images.githubusercontent.com/1786886/142641664-5e5450c0-616e-473d-b1bb-43f1cc7a8161.png)

It can also crop, output ANSI colour, adjust contrast/colour balance/brightness, invert, and other nice stuff, as well as render HTML.

## Installation

### From PyPI

```shell
# Minimal install:
pip install image2ascii
# Install with WSGI capabilities (see below):
pip install image2ascii[www]
```

### From source

```shell
# You do use virtual envs, right?
python3 -m venv .venv
source .venv/bin/activate
# Minimal install:
pip install -e .
# Install with WSGI capabilities (see below):
pip install -e .[www]
```

## Usage

### CLI

Installation per instructions above creates an `image2ascii` command; run it for more info. Play around with various combinations of `--invert`, `--negative`, `--contrast`, `--brightness`, and `--color-balance`, until the results are to your liking. `--color` and `--crop` are also highly recommended.

### WSGI

Image2ASCII can run as a simple WSGI application, courtesy of Flask. Just make sure you have installed it with the necessary extra requirements, either by running `pip install image2ascii[www]` or manually installing `Flask` and `requests`.

For this purpose, a fully working web implementation is also included. Not only does it leverage Image2ASCII's various features, it also enables drag-and-drop and pasting of images, and includes [all sovereign state flags](https://en.wikipedia.org/wiki/Gallery_of_sovereign_state_flags) from Wikipedia for the user to choose from. A live version is (at the time of writing) available [here](https://image2ascii.azurewebsites.net/).

Installation via `pip` will also create an `image2ascii_testserver` command with an optional port number argument (default is port 8000). Use it to fire up a basic web server on localhost and try it out. (Executing `wsgi.py` directly from the command line achieves the same thing.)

Here is a suggested (albeit untested) [Supervisor](http://supervisord.org/) setup:

`/etc/supervisor/conf.d/image2ascii.ini`:
```ini
[program:image2ascii]
directory = /path/to/image2ascii
command = /path/to/image2ascii/.venv/bin/uwsgi --ini config.ini
```

`/path/to/image2ascii/config.ini`:
```ini
[uwsgi]
module = image2ascii.wsgi:application
master = true
processes = 5
socket = /tmp/image2ascii.sock
chmod-socket = 666
vacuum = true
```

## Configuration

The CLI looks for config files in these locations, by order of priority:

* Path set via `--config` parameter
* `~/.image2ascii`
* `defaults.conf` in application directory (i.e. the directory where `config.py` is located)

The WSGI application looks for these config files, by order of priority:

* `web_defaults.conf` in application directory (a default one is included)
* `~/.image2ascii`
* `defaults.conf` in application directory

Config files follow a normal INI file structure (`key=value`). For available keys, refer to `config.py` (more specifically: `config.Config._fields`).

## Everything else

This project is totally in beta, and so its API should not be considered stable.

Shouts out to:
* [Pillow](https://python-pillow.org/)
* [Matplotlib](https://matplotlib.org/)
* [Colorama](https://github.com/tartley/colorama)
* [Numpy](https://numpy.org/)
* [Flask](https://flask.palletsprojects.com/)
