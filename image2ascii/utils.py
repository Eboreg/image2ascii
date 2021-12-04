import functools
import re
import time
from pathlib import Path
from typing import Dict, List, Tuple

from image2ascii import __version__

timings: List[Tuple[str, float]] = []
timing_enabled = False


def shorten_string(string: str, max_length: int) -> str:
    """max_length is excluding trailing ellipsis."""
    if len(string) > max_length:
        return string[:max_length] + " ..."
    return string


def timer(func):
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        if not timing_enabled:
            return func(*args, **kwargs)
        start_time = time.monotonic()
        ret = func(*args, **kwargs)
        elapsed_time = time.monotonic() - start_time
        timings.append((func.__qualname__, elapsed_time))
        return ret
    return wrapper


def summarize_timing():
    result: Dict[str, Tuple[int, float]] = {}
    for funcname, timing in timings:
        if funcname in result:
            result[funcname] = (result[funcname][0] + 1, result[funcname][1] + timing)
        else:
            result[funcname] = (1, timing)
    result_tuples = [(k, *v) for k, v in result.items()]
    return sorted(result_tuples, key=lambda r: r[-1])


def fetch_flags():
    """
    Flags are included in the project, this function only has to be run if
    they need to be updated for some reason (perhaps Republika Srpska will
    become independent?). For this reason, BeautifulSoup is not part of this
    project's requirements.
    """
    import requests
    from bs4 import BeautifulSoup

    flag_dir = Path(__file__).parent / "flags"
    user_agent = f"image2ascii/{__version__} (https://github.com/Eboreg/image2ascii)"
    headers = {"User-Agent": user_agent}
    response = requests.get("https://en.wikipedia.org/wiki/Gallery_of_sovereign_state_flags", headers=headers)
    soup = BeautifulSoup(response.content, "html.parser")

    for gallerybox in soup.select(".gallerybox"):
        name = gallerybox.select_one(".gallerytext>p>a").text
        name = re.sub(r"^Flag of ", "", name)
        name = re.sub(r"^the ", "", name, flags=re.IGNORECASE)

        url = gallerybox.select_one("img")["src"]
        url = re.sub(r"/\d+px-(.*)$", r"/640px-\1", url)
        if url.startswith("//"):
            url = "https:" + url

        response = requests.get(url, headers=headers)

        if response.status_code != 200:
            print(f" ** ERROR trying to get {url}, status code={response.status_code}")

        else:
            content_type = response.headers["Content-Type"]
            if content_type == "image/png":
                extension = "png"
            elif content_type == "image/jpeg":
                extension = "jpg"
            elif content_type == "image/gif":
                extension = "gif"
            else:
                print(f" ** ERROR: Unsupported content type {content_type}")
                continue
            filename = f"{name}.{extension}"
            with open(flag_dir / filename, "wb") as f:
                f.write(response.content)
            print(f"Saved {filename}")
