import tempfile
import zipfile
from collections.abc import Callable
from pathlib import Path

import requests

from image2ascii.logging import get_logger
from image2ascii_emoji.constants import (
    EMOJI_COLLECTION_PATH,
    EMOJI_LIST_URL,
    EMOJI_MODIFIER_URL,
    EMOJI_SVG_PATH,
    FLAG_SVG_PATH,
    NOTO_EMOJI_REPO_URL,
)
from image2ascii_emoji.data import EmojiCollection


logger = get_logger(__name__)


def completer(*args, **kwargs) -> list[str]:
    if collection := get_emoji_collection():
        return [emoji.slug for emoji in collection.all_emojis]
    return []


def download_svgs(
    emoji_dir: Path = EMOJI_SVG_PATH,
    flag_dir: Path = FLAG_SVG_PATH,
    noto_emoji_repo_url: str = NOTO_EMOJI_REPO_URL,
    callback: Callable[[str, bool], None] | None = None,
):
    """callback: callable("status text", linebreak)"""
    emoji_dir.mkdir(parents=True, exist_ok=True)
    flag_dir.mkdir(parents=True, exist_ok=True)

    with tempfile.NamedTemporaryFile(suffix=".zip") as temp_zip:
        with requests.get(noto_emoji_repo_url, stream=True) as response:
            if callback:
                callback(f"Downloading {noto_emoji_repo_url} ...", True)

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
                callback(f"Extracting flags to {flag_dir} ...", True)

            for flag in zip_flag_path.iterdir():
                if flag.is_file():
                    with (flag_dir / flag.name).open("wb") as f:
                        f.write(flag.read_bytes())
                        flag_count += 1

            if callback:
                callback(f"Extracting emojis to {emoji_dir} ...", True)

            for emoji in zip_emoji_path.iterdir():
                if emoji.is_file():
                    with (emoji_dir / emoji.name).open("wb") as f:
                        f.write(emoji.read_bytes())
                        emoji_count += 1

            if callback:
                callback(f"Extracted {flag_count} flags and {emoji_count} emojis.", True)


def get_emoji_collection(emoji_collection_path: Path = EMOJI_COLLECTION_PATH) -> EmojiCollection | None:
    if emoji_collection_path.is_file():
        try:
            with emoji_collection_path.open("rt") as f:
                return EmojiCollection.model_validate_json(f.read())
        except Exception:
            logger.error(f"Error opening/validating {emoji_collection_path}", exc_info=True)

    return None


def reload_emoji_collection(
    list_url: str = EMOJI_LIST_URL,
    modifiers_url: str = EMOJI_MODIFIER_URL,
    emoji_collection_path: Path = EMOJI_COLLECTION_PATH,
) -> EmojiCollection:
    emoji_collection_path.parent.mkdir(parents=True, exist_ok=True)
    collection = EmojiCollection.scrape(list_url=list_url, modifiers_url=modifiers_url)

    with emoji_collection_path.open("wt") as f:
        f.write(collection.model_dump_json(indent=2))

    return collection
