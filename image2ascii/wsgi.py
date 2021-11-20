from datetime import timedelta
from pathlib import Path
from typing import Any, Dict, Optional

from jinja2 import Environment, PackageLoader
from werkzeug.wrappers import Request, Response

from image2ascii.core import Image2ASCII
from image2ascii.db import Session, ShelfDB
from image2ascii.output import HTMLFormatter


class Application:
    # http://wsgi.tutorial.codepoint.net/application-interface
    # https://www.toptal.com/python/pythons-wsgi-server-application-interface

    def __init__(self):
        self.db = ShelfDB()
        self.flag_dir = Path(__file__).parent / "flags"

    def __call__(self, environ, start_response):
        request = Request(environ)
        session = self.get_session(request)
        response = self.get_response(request, session)
        return response(environ, start_response)

    def get_session(self, request: Request) -> Session:
        try:
            return self.db.get_session(request.cookies["session_id"])
        except KeyError:
            # Could be because cookie doesn't exist, or session doesn't
            return Session()

    def get_context(self, request: Request, session: Session) -> dict:
        context: Dict[str, Any] = dict(
            contrast=1.0,
            brightness=1.0,
            color_balance=1.0,
            flags=self.get_flags(),
        )
        if request.method == "POST":
            context.update(
                color="color" in request.form,
                invert="invert" in request.form,
                crop="crop" in request.form,
                invert_colors="invert-colors" in request.form,
                swap_bw="swap-bw" in request.form,
                fill_all="fill-all" in request.form,
                contrast=request.form.get("contrast", 1),
                brightness=request.form.get("brightness", 1),
                color_balance=request.form.get("color-balance", 1),
                selected_flag=request.form.get("flag"),
            )

            try:
                i2a = self.get_i2a(request, session.i2a)
                session.i2a = i2a
                context.update(
                    output=i2a.render(),
                    filename=i2a.filename,
                )
            except Exception as e:
                context.update(output=str(e))
        else:
            context.update(
                color=True,
                invert=False,
                crop=True,
                invert_colors=False,
                swap_bw=False,
                fill_all=False,
            )
            if session.i2a:
                context.update(
                    output=session.i2a.render(),
                    filename=session.i2a.filename,
                    color=session.i2a.color,
                    invert=session.i2a.invert,
                    crop=session.i2a.crop,
                    invert_colors=session.i2a.invert_colors,
                    swap_bw=session.i2a.swap_bw,
                    fill_all=session.i2a.fill_all,
                    contrast=session.i2a.contrast,
                    brightness=session.i2a.brightness,
                    color_balance=session.i2a.color_balance,
                )
        return context

    def get_flags(self):
        for flag_file in sorted(self.flag_dir.iterdir()):
            if flag_file.is_file():
                yield dict(value=flag_file.name, text=flag_file.stem)

    def get_html(self, context: dict) -> str:
        jinja = Environment(loader=PackageLoader("image2ascii", "templates"))
        template = jinja.get_template("index.html")
        return template.render(context)

    def get_response(self, request: Request, session: Session) -> Response:
        if request.path != "/":
            return Response("What are you trying to do?", status=404)
        if request.method == "HEAD":
            return Response()
        html = self.get_html(self.get_context(request, session))
        self.db.save_session(session)
        response = Response(html, mimetype="text/html")
        if request.cookies.get("session_id") != session.uuid:
            response.set_cookie("session_id", session.uuid, max_age=timedelta(days=7))
        return response

    def get_i2a(self, request: Request, i2a: Optional[Image2ASCII]) -> Image2ASCII:
        file = request.files.get("image")
        flag = request.form.get("flag") or None

        if file is not None and not file.filename:
            file = None

        if file is None and i2a is None and flag is None:
            raise ValueError("You need to upload an image or select a flag.")
        if i2a is None:
            i2a = Image2ASCII()

        if file is not None:
            i2a.load(file)
        elif flag is not None:
            i2a.load(self.flag_dir / flag)

        i2a.formatter_class = HTMLFormatter
        i2a.color_settings(
            color="color" in request.form,
            invert="invert" in request.form,
            invert_colors="invert-colors" in request.form,
            fill_all="fill-all" in request.form,
            swap_bw="swap-bw" in request.form
        )
        i2a.enhancement_settings(
            contrast=float(request.form["contrast"]),
            brightness=float(request.form["brightness"]),
            color_balance=float(request.form["color-balance"]),
        )
        i2a.size_settings(crop="crop" in request.form)

        return i2a


application = Application()
