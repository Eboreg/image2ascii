from image2ascii.config import get_app_dirs


USER_DATA_PATH = get_app_dirs().user_data_path

EMOJI_COLLECTION_PATH = USER_DATA_PATH / "emojis.json"
EMOJI_LIST_URL = "https://www.unicode.org/emoji/charts-17.0/emoji-list.html"
EMOJI_MODIFIER_URL = "https://www.unicode.org/emoji/charts-17.0/full-emoji-modifiers.html"
EMOJI_SVG_PATH = USER_DATA_PATH / "svg/emojis"
FLAG_SVG_PATH = USER_DATA_PATH / "svg/flags"
NOTO_EMOJI_REPO_URL = "https://github.com/googlefonts/noto-emoji/archive/refs/heads/main.zip"
