#!/usr/bin/env python3

import base64
import io
import os
import sys
from pathlib import Path
from typing import TYPE_CHECKING
from urllib.parse import urlparse
from uuid import uuid4
from wsgiref.simple_server import make_server

import requests
from flask import Flask, Request, jsonify, redirect, request

from image2ascii import __version__
from image2ascii.color import HTMLANSIColorConverter, HTMLFullRGBColorConverter
from image2ascii.config import Config
from image2ascii.core import Image2ASCII
from image2ascii.db import ShelfDB
from image2ascii.utils import shorten_string

if TYPE_CHECKING:
    from _typeshed import SupportsRead

FLAG_DIR = Path(__file__).parent / "flags"
UPLOADS_DIR = Path(__file__).parent / "uploads"
DB = ShelfDB()

application = Flask(__name__)
os.makedirs(UPLOADS_DIR, exist_ok=True)


def fetch_remote_image(url: str) -> io.BytesIO:
    try:
        headers = {"User-Agent": f"image2ascii/{__version__} (https://github.com/Eboreg/image2ascii)"}
        response = requests.get(url, headers=headers, timeout=5.0)
    except Exception as e:
        raise ValueError(f"Could not fetch image file: {shorten_string(str(e), 200)}") from e
    if response.status_code != 200:
        raise ValueError(f"Could not fetch image file (HTTP status code={response.status_code}).")
    if not isinstance(response.content, bytes):
        raise ValueError(f"Could not fetch image file (response content has type '{type(response.content)}').")
    if not response.content:
        raise ValueError("Could not fetch image file (response is empty).")
    return io.BytesIO(response.content)


def generate_filename(basename: str) -> Path:
    return UPLOADS_DIR / (os.path.splitext(basename)[0] + "-" + uuid4().hex + ".png")


def get_config(request: Request | None = None) -> Config:
    try:
        config = Config.from_file(Path(__file__).parent / "web_defaults.conf")
    except Exception:
        config = Config.from_default_files()

    if request and request.is_json and request.json:
        config.update(
            color=request.json["checkboxes"]["color"],
            invert=request.json["checkboxes"]["invert"],
            negative=request.json["checkboxes"]["negative"],
            fill_all=request.json["checkboxes"]["fill-all"],
            crop=request.json["checkboxes"]["crop"],
            full_rgb=request.json["checkboxes"]["full-rgb"],
            contrast=float(request.json["sliders"]["contrast"]),
            brightness=float(request.json["sliders"]["brightness"]),
            color_balance=float(request.json["sliders"]["color-balance"]),
        )

        if config.full_rgb:
            config.color_converter_class = HTMLFullRGBColorConverter
        else:
            config.color_converter_class = HTMLANSIColorConverter

    return config


def get_checkboxes(config: Config) -> dict[str, bool]:
    return {
        "color": config.color,
        "crop": config.crop,
        "invert": config.invert,
        "negative": config.negative,
        "fill-all": config.fill_all,
        "full-rgb": config.full_rgb,
    }


def get_context(config: Config, **kwargs) -> dict:
    return {
        "version": __version__,
        "checkboxes": get_checkboxes(config=config),
        "sliders": {
            "contrast": config.contrast,
            "brightness": config.brightness,
            "color-balance": config.color_balance,
        },
        **kwargs,
    }


def get_flags():
    return [{"value": file.name, "text": file.stem} for file in sorted(FLAG_DIR.iterdir()) if file.is_file()]


def get_session(uuid: str, config: Config | None = None):
    """Raises KeyError if session is not found in DB"""
    sess = DB.get(uuid)
    if config is not None:
        sess = DB.update(uuid, config)
    return sess


def post_image(image: "str | bytes | Path | SupportsRead[bytes]", filename: str | Path):
    config = get_config(request)
    i2a = Image2ASCII(file=image, config=config)
    image_hash = i2a.image_hash
    sess = DB.get_by_hash(image_hash)

    if sess is None:
        i2a.save_image(filename=filename)
        sess = DB.create(filename, config, hash=image_hash)
    else:
        sess = DB.update(sess.uuid, config)

    output = i2a.render()
    context = get_context(config, uuid=sess.uuid, output=output)

    return jsonify(context)


@application.route("/flags")
def flags():
    return jsonify(get_flags())


@application.route("/json")
def json():
    context = None

    if "uuid" in request.args:
        try:
            sess = get_session(request.args["uuid"])
            i2a = Image2ASCII(file=sess.filename, config=sess.config)
            output = i2a.render()
            context = get_context(sess.config, uuid=sess.uuid, output=output, flag=sess.flag)
        except KeyError:
            # Probably requested an old or invalid URL; redirect to base
            return redirect(request.base_url)

    if context is None:
        context = get_context(get_config())

    return jsonify(context)


@application.route("/post", methods=["POST"])
def post():
    assert request.json
    sess = get_session(request.json["uuid"])
    config = get_config(request)
    sess = DB.update(sess.uuid, config)
    i2a = Image2ASCII(file=sess.filename, config=config)
    output = i2a.render()
    context = get_context(config, uuid=sess.uuid, output=output, flag=sess.flag)

    return jsonify(context)


@application.route("/post-file", methods=["POST"])
def post_file():
    assert request.json

    filename = generate_filename(request.json["file"]["name"])
    image = io.BytesIO(base64.b64decode(request.json["file"]["contents"]))
    response = post_image(image=image, filename=filename)
    image.close()

    return response


@application.route("/post-flag", methods=["POST"])
def post_flag():
    assert request.json
    flag = request.json["flag"]
    config = get_config(request)

    filename = FLAG_DIR / flag
    i2a = Image2ASCII(file=filename, config=config)
    output = i2a.render()
    sess = DB.create(filename, config, keep_file=True, flag=flag)
    context = get_context(config, uuid=sess.uuid, output=output, flag=flag)

    return jsonify(context)


@application.route("/post-url", methods=["POST"])
def post_url():
    assert request.json
    url = request.json["url"]
    assert isinstance(url, str)

    filename = generate_filename(urlparse(url).path.split("/")[-1])
    image = fetch_remote_image(url)
    response = post_image(image=image, filename=filename)
    image.close()

    return response


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
