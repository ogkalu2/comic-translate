import os

from modules.utils.paths import get_user_data_dir

user_font_path = os.path.join(get_user_data_dir(), "fonts")
os.makedirs(user_font_path, exist_ok=True)

supported_target_languages = [
    # "English",
    "Korean",
    "Japanese",
    "French",
    # "Simplified Chinese",
    "Traditional Chinese",
    "Russian",
    "German",
    # "Dutch",
    "Spanish",
    "Italian",
    "Turkish",
    "Polish",
    # "Portuguese",
    "Brazilian Portuguese",
    # "Thai",
    # "Vietnamese",
    # "Hungarian",
    "Indonesian",
    # "Finnish",
    # "Arabic",
    # "Czech",
    # "Persian",
    # "Romanian",
    # "Mongolian",
]

supported_ocr_language_hints = [
    "Japanese",
    "Korean",
    "Other Languages",
]
