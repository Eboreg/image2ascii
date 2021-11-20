import re
from pathlib import Path

import requests
from bs4 import BeautifulSoup

from image2ascii import __version__


def fetch_flags():
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
