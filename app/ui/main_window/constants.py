import os

from modules.utils.paths import get_user_data_dir

user_font_path = os.path.join(get_user_data_dir(), "fonts")
os.makedirs(user_font_path, exist_ok=True)

supported_source_languages = [
    "Korean",
    "Japanese",
    "French",
    "Chinese",
    "English",
    "Russian",
    "German",
    "Dutch",
    "Spanish",
    "Italian",
]

supported_target_languages = [
    "English",
    "Korean",
    "Japanese",
    "French",
    "Simplified Chinese",
    "Traditional Chinese",
    "Russian",
    "German",
    "Dutch",
    "Spanish",
    "Italian",
    "Turkish",
    "Polish",
    "Portuguese",
    "Brazilian Portuguese",
    "Thai",
    "Vietnamese",
    "Hungarian",
    "Indonesian",
    "Finnish",
    "Arabic",
    "Hebrew",
    "Czech",
    "Persian",
    "Romanian",
    "Mongolian",
]
