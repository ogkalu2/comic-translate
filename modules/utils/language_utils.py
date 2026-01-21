from PySide6.QtCore import Qt

language_codes = {
    "Korean": "ko",
    "Japanese": "ja",
    "Chinese": "zh",
    "Simplified Chinese": "zh-CN",
    "Traditional Chinese": "zh-TW",
    "English": "en",
    "Russian": "ru",
    "French": "fr",
    "German": "de",
    "Dutch": "nl",
    "Spanish": "es",
    "Italian": "it",
    "Turkish": "tr",
    "Polish": "pl",
    "Portuguese": "pt",
    "Brazilian Portuguese": "pt-br",
    "Thai": "th",
    "Vietnamese": "vi",
    "Indonesian": "id",
    "Hungarian": "hu",
    "Finnish": "fi",
    "Arabic": "ar",
    "Czech": "cs",
    "Persian": "fa",
    "Romanian": "ro",
    "Mongolian": "mn",
}

def get_layout_direction(language: str) -> Qt.LayoutDirection:
    return Qt.LayoutDirection.RightToLeft if language == 'Arabic' else Qt.LayoutDirection.LeftToRight

def get_language_code(lng: str):
    lng_cd = language_codes.get(lng, None)
    return lng_cd

def is_no_space_lang(lang_code: str | None) -> bool:
    """
    Check if the language usually does not use spaces between words.
    Includes: Chinese (zh), Japanese (ja), Thai (th).
    """
    if not lang_code:
        return False
    code = lang_code.lower()
    return any(lang in code for lang in ['zh', 'ja', 'th'])
