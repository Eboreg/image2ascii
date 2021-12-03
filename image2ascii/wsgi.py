import io
from datetime import timedelta
from pathlib import Path
from typing import Any, Dict, Optional

import requests
from flask import Flask, jsonify, make_response, render_template, request
from werkzeug.wrappers import Request

from image2ascii.color import HTMLANSIColorConverter, HTMLFullRGBColorConverter
from image2ascii.core import Image2ASCII
from image2ascii.db import Session, ShelfDB
from image2ascii.output import HTMLFormatter

ASCII_MAX_HEIGHT = 150
FLAG_DIR = Path(__file__).parent / "flags"
DB = ShelfDB()

application = Flask(__name__)


def get_flags():
    for flag_file in sorted(FLAG_DIR.iterdir()):
        if flag_file.is_file():
            yield dict(value=flag_file.name, text=flag_file.stem)


def get_i2a(request: Request, i2a: Optional[Image2ASCII]) -> Image2ASCII:
    image: Any = request.files.get("image")
    image_url = request.form.get("image-url") or None
    flag = request.form.get("flag") or None

    if image is not None and not image.filename:
        image = None

    if image is None and image_url is not None:
        try:
            response = requests.get(image_url, timeout=5.0)
        except Exception:
            raise ValueError("Could not fetch image file -- possibly timeout.")
        if response.status_code != 200 or not isinstance(response.content, bytes) or not len(response.content):
            raise ValueError("Could not fetch image file.")
        image = io.BytesIO(response.content)

    if image is None and i2a is None and flag is None:
        raise ValueError("You need to upload an image or select a flag.")
    if i2a is None:
        i2a = Image2ASCII()

    if image is not None:
        i2a.load(image)
        if hasattr(image, "close"):
            image.close()
    elif flag is not None:
        i2a.load(FLAG_DIR / flag)

    i2a.formatter_class = HTMLFormatter

    if "full-rgb" in request.form:
        i2a.color_converter_class = HTMLFullRGBColorConverter
    else:
        i2a.color_converter_class = HTMLANSIColorConverter

    i2a.color_settings(
        color="color" in request.form,
        invert="invert" in request.form,
        negative="negative" in request.form,
        fill_all="fill-all" in request.form,
    )

    i2a.enhancement_settings(
        contrast=float(request.form["contrast"]),
        brightness=float(request.form["brightness"]),
        color_balance=float(request.form["color-balance"]),
    )

    i2a.size_settings(crop="crop" in request.form, ascii_max_height=ASCII_MAX_HEIGHT)

    return i2a


def get_context(session: Session) -> dict:
    context: Dict[str, Any] = dict(flags=get_flags())

    if session.i2a:
        context.update(
            output=session.i2a.render(),
            color=session.i2a.color,
            invert=session.i2a.invert,
            crop=session.i2a.crop,
            negative=session.i2a.negative,
            fill_all=session.i2a.fill_all,
            full_rgb=session.i2a.color_converter_class is not HTMLANSIColorConverter,
            contrast=session.i2a.contrast,
            brightness=session.i2a.brightness,
            color_balance=session.i2a.color_balance,
        )
    else:
        context.update(
            color=True,
            invert=False,
            crop=True,
            negative=False,
            fill_all=False,
            full_rgb=True,
            contrast=1.0,
            brightness=1.0,
            color_balance=1.0,
        )

    return context


def get_session(id: str) -> Session:
    try:
        return DB.get_session(id)
    except KeyError:
        return Session()


@application.route("/")
def index():
    session = get_session(request.cookies["session_id"])
    context = get_context(session)
    DB.save_session(session)
    response = make_response(render_template("index.html", **context))
    if request.cookies.get("session_id") != session.uuid:
        response.set_cookie("session_id", session.uuid, max_age=timedelta(days=7))
    return response


@application.route("/post", methods=["POST"])
def post():
    session = get_session(request.cookies["session_id"])
    try:
        i2a = get_i2a(request, session.i2a)
        session.i2a = i2a
        response = jsonify(output=i2a.render())
        DB.save_session(session)
        return response
    except Exception as e:
        return jsonify(output=str(e))
