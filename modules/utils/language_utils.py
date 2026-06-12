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
    "Hebrew": "he",
    "Czech": "cs",
    "Croatian": "hr",
    "Persian": "fa",
    "Romanian": "ro",
    "Mongolian": "mn",
}

def get_layout_direction(language: str) -> Qt.LayoutDirection:
    rtl_languages = {"Arabic", "Hebrew", "Persian"}
    return Qt.LayoutDirection.RightToLeft if language in rtl_languages else Qt.LayoutDirection.LeftToRight

def get_language_code(lng: str):
    lng_cd = language_codes.get(lng, None)
    return lng_cd

# Mapping from OSD script-detection labels to the OCR engine "buckets" 
# used by OCRFactory when source language is "Auto".
SCRIPT_TO_OCR_BUCKET = {
    "Latin": "latin",
    "Cyrillic": "cyrillic",
    "Japanese": "japanese",
    "Hangul": "korean",
    "HanS": "chinese",
    "HanT": "chinese",
}

# Mapping from OSD script-detection labels to ISO-ish language codes used for
# blk.source_lang (e.g. for is_no_space_lang / text joining behavior).
SCRIPT_TO_LANG_CODE = {
    "Latin": "en",
    "Cyrillic": "ru",
    "Japanese": "ja",
    "Hangul": "ko",
    "HanS": "zh",
    "HanT": "zh",
}


def normalize_script(script: str) -> str:
    """Strip OSD '_vert'/'-dn' suffixes, returning the base script name."""
    base = script or ""
    while True:
        for suffix in ("-dn", "_vert"):
            if base.endswith(suffix):
                base = base[: -len(suffix)]
                break
        else:
            return base


def get_ocr_bucket_for_script(script: str) -> str:
    """Resolve a detected OSD script label to an OCR engine bucket, defaulting to 'latin'."""
    return SCRIPT_TO_OCR_BUCKET.get(normalize_script(script), "latin")


def get_lang_code_for_script(script: str) -> str:
    """Resolve a detected OSD script label to a language code, defaulting to 'en'."""
    return SCRIPT_TO_LANG_CODE.get(normalize_script(script), "en")


def is_supported_script(script: str) -> bool:
    """Return whether a detected script cleanly maps to an OCR routing bucket."""
    return normalize_script(script) in SCRIPT_TO_OCR_BUCKET


def is_no_space_lang(lang_code: str | None) -> bool:
    """
    Check if the language usually does not use spaces between words.
    Includes: Chinese (zh), Japanese (ja), Thai (th).
    """
    if not lang_code:
        return False
    code = lang_code.lower()
    return any(lang in code for lang in ['zh', 'ja', 'th'])
