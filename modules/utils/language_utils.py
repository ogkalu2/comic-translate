from PySide6.QtCore import Qt
import re

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

RTL_LANGUAGE_CODES = {
    "ar",  # Arabic
    "fa",  # Persian/Farsi
    "he",  # Hebrew
    "iw",  # Legacy Hebrew code
    "ur",  # Urdu
    "ps",  # Pashto
    "sd",  # Sindhi
    "ug",  # Uyghur
    "yi",  # Yiddish
}


def is_rtl_language_code(lang_code: str | None) -> bool:
    if not lang_code:
        return False
    return lang_code.split("-", 1)[0].lower() in RTL_LANGUAGE_CODES


def get_layout_direction(language: str | None) -> Qt.LayoutDirection:
    return (
        Qt.LayoutDirection.RightToLeft
        if is_rtl_language_code(get_language_code(language) or language)
        else Qt.LayoutDirection.LeftToRight
    )

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


_NO_SPACE_TEXT_RE = re.compile(r"[\u3040-\u30ff\u3400-\u9fff\uf900-\ufaff\uac00-\ud7af\u0e00-\u0e7f]")


def is_no_space_text(text: str | None) -> bool:
    """Heuristic for scripts that are typically written without spaces."""
    if not text:
        return False
    return bool(_NO_SPACE_TEXT_RE.search(text))
