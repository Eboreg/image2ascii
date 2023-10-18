#!/usr/bin/env python3

import io
import os
import sys
from pathlib import Path
from typing import Optional, Tuple
from urllib.parse import urlparse
from uuid import uuid4
from wsgiref.simple_server import make_server

import requests
from flask import Flask, Request, jsonify, make_response, redirect, render_template, request
from werkzeug.datastructures import FileStorage

from image2ascii import __version__
from image2ascii.color import HTMLANSIColorConverter, HTMLFullRGBColorConverter
from image2ascii.config import Config
from image2ascii.core import Image2ASCII
from image2ascii.db import ShelfDB
from image2ascii.utils import shorten_string

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


def get_config(request: Optional[Request] = None) -> Config:
    try:
        config = Config.from_file(Path(__file__).parent / "web_defaults.conf")
    except Exception:
        config = Config.from_default_files()

    if request is not None:
        config.update(
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

        if config.full_rgb:
            config.color_converter_class = HTMLFullRGBColorConverter
        else:
            config.color_converter_class = HTMLANSIColorConverter

    return config


def get_context(config: Config, **kwargs) -> dict:
    return {
        "flags": get_flags(),
        "version": __version__,
        "color": config.color,
        "invert": config.invert,
        "crop": config.crop,
        "negative": config.negative,
        "fill_all": config.fill_all,
        "full_rgb": config.full_rgb,
        "contrast": config.contrast,
        "brightness": config.brightness,
        "color_balance": config.color_balance,
        **kwargs,
    }


def get_flags():
    for flag_file in sorted(FLAG_DIR.iterdir()):
        if flag_file.is_file():
            yield {"value": flag_file.name, "text": flag_file.stem}


def get_session(uuid: str, config: Optional[Config] = None):
    """Raises KeyError if session is not found in DB"""
    session = DB.get(uuid)
    if config is not None:
        session = DB.update(uuid, config)
    return session


def render(request: Request) -> Tuple[Optional[str], Optional[str]]:
    """
    Gets/creates Image2ASCII object, renders it, saves it to DB.
    Returns: (uuid, output)
    """
    config = get_config(request)

    # 1. Try uploaded image
    uploaded_image = request.files.get("image")
    if uploaded_image and uploaded_image.filename:
        return render_from_upload(uploaded_image, config)

    # 2. Try pasted image URL
    if request.form.get("image-url"):
        return render_from_url(request.form["image-url"], config)

    # 3. Try selected flag
    if request.form.get("flag"):
        return render_from_flag(request.form["flag"], config)

    # 4. Try UUID
    if request.form.get("uuid"):
        return render_from_uuid(request.form["uuid"], config)

    return None, None


def render_from_flag(flag: str, config: Config) -> Tuple[str, str]:
    filename = FLAG_DIR / flag
    i2a = Image2ASCII(file=filename, config=config)
    assert i2a.image is not None, "Could not load image"
    output = i2a.render()
    session = DB.create(filename, config, keep_file=True)
    return session.uuid, output


def render_from_upload(image: FileStorage, config: Config) -> Tuple[str, str]:
    assert image.filename is not None
    filename = generate_filename(image.filename)
    i2a = Image2ASCII(file=image, config=config)
    image.close()
    assert i2a.image is not None, "Could not load image"
    image_hash = hash(tuple(i2a.image.getdata()))
    session = DB.get_by_hash(image_hash)
    if session is None:
        i2a.image.save(filename)
        session = DB.create(filename, config, hash=image_hash)
    else:
        session = DB.update(session.uuid, config)
    output = i2a.render()
    return session.uuid, output


def render_from_url(url: str, config: Config) -> Tuple[str, str]:
    filename = generate_filename(urlparse(url).path.split("/")[-1])
    image = fetch_remote_image(url)
    i2a = Image2ASCII(file=image, config=config)
    image.close()
    assert i2a.image is not None, "Could not load image"
    image_hash = hash(tuple(i2a.image.getdata()))
    session = DB.get_by_hash(image_hash)
    if session is None:
        i2a.image.save(filename)
        session = DB.create(filename, config, hash=image_hash)
    else:
        session = DB.update(session.uuid, config)
    output = i2a.render()
    return session.uuid, output


def render_from_uuid(uuid: str, config: Optional[Config] = None) -> Tuple[Optional[str], Optional[str]]:
    """If session not found in DB, just return uuid=None and empty output"""
    try:
        session = get_session(uuid, config)
        i2a = Image2ASCII(file=session.filename, config=session.config)
        output = i2a.render()
        return session.uuid, output
    except KeyError:
        return None, None


@application.route("/")
def index():
    context = None

    if "uuid" in request.args:
        try:
            session = get_session(request.args["uuid"])
            i2a = Image2ASCII(file=session.filename, config=session.config)
            output = i2a.render()
            context = get_context(session.config, uuid=session.uuid, output=output)
        except KeyError:
            # Probably requested an old or invalid URL; redirect to base
            return redirect(request.base_url)

    if context is None:
        context = get_context(get_config())

    response = make_response(render_template("index.html", **context))
    return response


@application.route("/post", methods=["POST"])
def post():
    try:
        uuid, output = render(request)
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
