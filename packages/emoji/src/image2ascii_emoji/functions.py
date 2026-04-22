import tempfile
import zipfile
from collections.abc import Callable

import requests

from image2ascii_emoji.constants import (
    EMOJI_COLLECTION_PATH,
    EMOJI_LIST_URL,
    EMOJI_MODIFIER_URL,
    EMOJI_SVG_PATH,
    FLAG_SVG_PATH,
    NOTO_EMOJI_REPO_URL,
    USER_DATA_PATH,
)
from image2ascii_emoji.data import EmojiCollection


def download_svgs(callback: Callable[[str, bool], None] | None = None):
    """callable("status text", linebreak)"""
    ensure_svg_dirs_exist()

    with tempfile.NamedTemporaryFile(suffix=".zip") as temp_zip:
        with requests.get(NOTO_EMOJI_REPO_URL, stream=True) as response:
            if callback:
                callback(f"Downloading {NOTO_EMOJI_REPO_URL} ...", True)

            if response.status_code == 200 and response.headers.get("Content-Type", "") == "application/zip":
                # Guesstimating the size since Github won't let us know:
                total_size = 221347056
                read_bytes = 0
                percent = 0

                for chunk in response.iter_content(0xffff):
                    temp_zip.write(chunk)
                    read_bytes += len(chunk)
                    new_percent = (read_bytes / total_size) * 100

                    if new_percent >= percent + 10:
                        percent = int(new_percent)
                        if callback:
                            callback(f"{percent}% ... ", False)

                if callback:
                    if percent < 100:
                        callback("100%", True)
                    else:
                        callback("" , True)

        with zipfile.ZipFile(temp_zip) as noto_zip:
            zip_emoji_path = zipfile.Path(noto_zip, "noto-emoji-main/svg/")
            zip_flag_path = zipfile.Path(noto_zip, "noto-emoji-main/third_party/region-flags/svg/")
            flag_count = 0
            emoji_count = 0

            if callback:
                callback(f"Extracting flags to {FLAG_SVG_PATH} ...", True)

            for flag in zip_flag_path.iterdir():
                if flag.is_file():
                    with (FLAG_SVG_PATH / flag.name).open("wb") as f:
                        f.write(flag.read_bytes())
                        flag_count += 1

            if callback:
                callback(f"Extracting emojis to {EMOJI_SVG_PATH} ...", True)

            for emoji in zip_emoji_path.iterdir():
                if emoji.is_file():
                    with (EMOJI_SVG_PATH / emoji.name).open("wb") as f:
                        f.write(emoji.read_bytes())
                        emoji_count += 1

            if callback:
                callback(f"Extracted {flag_count} flags and {emoji_count} emojis.", True)


def ensure_svg_dirs_exist():
    EMOJI_SVG_PATH.mkdir(parents=True, exist_ok=True)
    FLAG_SVG_PATH.mkdir(parents=True, exist_ok=True)


def get_emoji_collection() -> EmojiCollection | None:
    if EMOJI_COLLECTION_PATH.is_file():
        try:
            with EMOJI_COLLECTION_PATH.open("rt") as f:
                return EmojiCollection.model_validate_json(f.read())
        except Exception:
            pass

    return None


def get_emoji_collection_interactive() -> EmojiCollection:
    if is_svg_download_needed():
        print(
            "Before you can use image2ascii-emoji, we need to do an automatic one-time download \n"
            "of image files from the Noto-Emoji font. The download is ~212 MB, and after extraction \n"
            f"~63 MB of SVG files will be placed under {USER_DATA_PATH}.\n"
        )
        reply = input("Do this download now? [Y/n] ").strip()
        if not reply or reply in "Yy":
            download_svgs(lambda status, br: print(status, end="\n" if br else "", flush=True))

    collection = get_emoji_collection()

    if collection is None:
        print(
            f"Got to do a one-time scraping of {EMOJI_LIST_URL}\n"
            f"and {EMOJI_MODIFIER_URL}.\n"
            "Just a moment ..."
        )
        collection = reload_emoji_collection()

    return collection


def is_svg_download_needed():
    ensure_svg_dirs_exist()
    return len(list(EMOJI_SVG_PATH.glob("*.svg"))) < 3000 or len(list(FLAG_SVG_PATH.glob("*.svg"))) < 300


def reload_emoji_collection(list_url: str = EMOJI_LIST_URL, modifiers_url: str = EMOJI_MODIFIER_URL) -> EmojiCollection:
    USER_DATA_PATH.mkdir(parents=True, exist_ok=True)
    collection = EmojiCollection.scrape(list_url, modifiers_url)

    with EMOJI_COLLECTION_PATH.open("wt") as f:
        f.write(collection.model_dump_json(indent=2))

    return collection
