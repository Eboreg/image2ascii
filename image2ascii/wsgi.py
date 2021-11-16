from typing import Tuple

from jinja2 import Environment, PackageLoader
from werkzeug.wrappers import Request

from image2ascii.color import ColorConverterInvertBW
from image2ascii.core import Image2ASCII
from image2ascii.output import HTMLFormatter


class Application:
    # http://wsgi.tutorial.codepoint.net/application-interface
    # https://www.toptal.com/python/pythons-wsgi-server-application-interface

    def __call__(self, environ, start_response):
        request = Request(environ)
        status, headers, body = self.get_response(request)
        start_response(status, headers)
        return [body]

    def get_context(self, request: Request) -> dict:
        context = dict(
            contrast=request.form.get("contrast", 1),
            brightness=request.form.get("brightness", 1),
            color_balance=request.form.get("color-balance", 1),
        )
        if request.method == "POST":
            context.update(
                output=self.render_uploaded_image(request),
                color="color" in request.form,
                invert="invert" in request.form,
                crop="crop" in request.form,
                invert_colors="invert-colors" in request.form,
                swap_bw="swap-bw" in request.form,
                fill_all="fill-all" in request.form,
            )
        else:
            context.update(
                color=True,
                invert=False,
                crop=True,
                invert_colors=False,
                swap_bw=False,
                fill_all=False,
            )
        return context

    def get_html(self, context: dict) -> str:
        jinja = Environment(loader=PackageLoader("image2ascii", "templates"))
        template = jinja.get_template("index.html")
        return template.render(context)

    def get_response(self, request: Request) -> Tuple[str, list, bytes]:
        if request.method == "HEAD":
            return "200 OK", [], b""
        html = self.get_html(self.get_context(request))
        headers = [
            ("Content-Type", "text/html"),
            ("Content-Length", str(len(html))),
        ]
        return "200 OK", headers, html.encode("utf-8")

    def render_uploaded_image(self, request: Request) -> str:
        try:
            file = request.files["image"]
            i2a = Image2ASCII(
                file,
                invert="invert" in request.form,
                fill_all="fill-all" in request.form
            )
            i2a.enhance(
                float(request.form["contrast"]),
                float(request.form["brightness"]),
                float(request.form["color-balance"])
            )
            if "invert-colors" in request.form:
                i2a.invert_colors()
            if "crop" in request.form:
                i2a.crop()
            if "swap-bw" in request.form:
                i2a.set_color_converter(ColorConverterInvertBW())
            i2a.prepare()
            return i2a.render(
                formatter=HTMLFormatter(),
                color="color" in request.form,
            )
        except Exception as e:
            return str(e)


application = Application()
