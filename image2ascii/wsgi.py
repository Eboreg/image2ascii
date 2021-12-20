#!/usr/bin/env python3

import io
import sys
from pathlib import Path
from typing import Any, Dict, Optional
from wsgiref.simple_server import make_server

import requests
from flask import Flask, Request, jsonify, make_response, render_template, request

from image2ascii import __version__
from image2ascii.color import HTMLANSIColorConverter, HTMLFullRGBColorConverter
from image2ascii.config import Config
from image2ascii.core import Image2ASCII
from image2ascii.db import ShelfDB
from image2ascii.utils import shorten_string

FLAG_DIR = Path(__file__).parent / "flags"
DB = ShelfDB()

application = Flask(__name__)


def get_flags():
    for flag_file in sorted(FLAG_DIR.iterdir()):
        if flag_file.is_file():
            yield dict(value=flag_file.name, text=flag_file.stem)


def get_i2a(request: Request) -> Image2ASCII:
    image: Any = request.files.get("image")
    image_url = request.form.get("image-url") or None
    flag = request.form.get("flag") or None
    i2a = DB.get_i2a(request.form["uuid"])

    if image is not None and not image.filename:
        image = None

    if image is None and image_url is not None:
        try:
            headers = {"User-Agent": f"image2ascii/{__version__} (https://github.com/Eboreg/image2ascii)"}
            response = requests.get(image_url, headers=headers, timeout=5.0)
        except Exception as e:
            raise ValueError(f"Could not fetch image file: {shorten_string(str(e), 200)}")
        if response.status_code != 200:
            raise ValueError(f"Could not fetch image file (HTTP status code={response.status_code}).")
        if not isinstance(response.content, bytes):
            raise ValueError(f"Could not fetch image file (response content has type '{type(response.content)}').")
        if not len(response.content):
            raise ValueError("Could not fetch image file (response is empty).")
        image = io.BytesIO(response.content)

    if image is None and i2a is None and flag is None:
        raise ValueError("You need to upload an image or select a flag.")

    if i2a is None:
        i2a = Image2ASCII(config=get_config())

    if image is not None:
        i2a.load(image)
        if hasattr(image, "close"):
            image.close()
    elif flag is not None:
        i2a.load(FLAG_DIR / flag)

    i2a.config.update(
        color="color" in request.form,
        invert="invert" in request.form,
        negative="negative" in request.form,
        fill_all="fill-all" in request.form,
        contrast=float(request.form["contrast"]),
        brightness=float(request.form["brightness"]),
        color_balance=float(request.form["color-balance"]),
        crop="crop" in request.form,
        full_rgb="full-rgb" in request.form,
    )

    if i2a.config.full_rgb:
        i2a.config.color_converter_class = HTMLFullRGBColorConverter
    else:
        i2a.config.color_converter_class = HTMLANSIColorConverter

    return i2a


def get_config() -> Config:
    try:
        return Config.from_file(Path(__file__).parent / "web_defaults.conf")
    except Exception:
        return Config.from_default_files()


def get_context(i2a: Optional[Image2ASCII], **kwargs) -> dict:
    context: Dict[str, Any] = dict(
        flags=get_flags(),
        version=__version__,
    )

    if i2a:
        config = i2a.config
        context.update(output=i2a.render())
    else:
        config = get_config()

    context.update(
        color=config.color,
        invert=config.invert,
        crop=config.crop,
        negative=config.negative,
        fill_all=config.fill_all,
        full_rgb=config.full_rgb,
        contrast=config.contrast,
        brightness=config.brightness,
        color_balance=config.color_balance,
        **kwargs
    )

    return context


@application.route("/")
def index():
    uuid = request.args.get("uuid")
    i2a = DB.get_i2a(uuid)
    context = get_context(i2a, uuid=uuid)
    response = make_response(render_template("index.html", **context))
    return response


@application.route("/post", methods=["POST"])
def post():
    try:
        uuid: Optional[str] = request.form["uuid"]
        i2a = get_i2a(request)
        output = i2a.render()
        uuid = DB.save_i2a(i2a, uuid)
        response = jsonify(output=output, uuid=uuid)
        return response
    except Exception as e:
        return jsonify(error=str(e))


def testserver():
    port = 8000

    if len(sys.argv) > 1:
        port = int(sys.argv[1])

    httpd = make_server("localhost", port, application)

    print(f"Listening on http://localhost:{port}; press Ctrl-C to break.")

    if len(sys.argv) <= 1:
        print("To use another port, run this command with that port number as only argument.")

    httpd.serve_forever()


if __name__ == "__main__":
    testserver()
