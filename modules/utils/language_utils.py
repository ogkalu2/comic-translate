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


def to_canonical_language_name(language: str, language_map: dict | None = None) -> str:
    """Convert a localized UI language label to its stable English identifier."""
    if language_map:
        return language_map.get(language, language)
    return language


def to_ui_language_label(language: str, reverse_language_map: dict | None = None) -> str:
    """Convert a canonical language name back to the current UI label."""
    if reverse_language_map:
        return reverse_language_map.get(language, language)
    return language

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

# Mapping from OSD script-detection labels to the source language names sent
# to remote OCR/translation APIs when "Auto" should be resolved to a concrete
# language. Latin is intentionally omitted because script alone cannot identify
# which Latin-script language the page uses.
SCRIPT_TO_SOURCE_LANGUAGE = {
    "Cyrillic": "Russian",
    "Japanese": "Japanese",
    "Hangul": "Korean",
    "HanS": "Chinese",
    "HanT": "Chinese",
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


def get_source_language_for_script(script: str) -> str:
    """Resolve a detected OSD script label to an English source-language name."""
    return SCRIPT_TO_SOURCE_LANGUAGE.get(normalize_script(script), "Auto")


def is_supported_script(script: str) -> bool:
    """Return whether a detected script cleanly maps to an OCR routing bucket."""
    return normalize_script(script) in SCRIPT_TO_OCR_BUCKET


def get_dominant_page_script(blocks: list, threshold: float = 0.7) -> str:
    """
    Derive a dominant page script from supported block scripts weighted by area.
    Returns an empty string when the page is mixed or there is no script data.
    """
    area_by_script: dict[str, float] = {}
    total_area = 0.0

    for block in blocks:
        script = normalize_script(getattr(block, "script", ""))
        if not is_supported_script(script):
            continue

        area = _block_area(block)
        area_by_script[script] = area_by_script.get(script, 0.0) + area
        total_area += area

    if not area_by_script or total_area <= 0.0:
        return ""

    dominant_script, dominant_area = max(area_by_script.items(), key=lambda item: item[1])
    if dominant_area / total_area < threshold:
        return ""
    return dominant_script


def resolve_auto_source_language(blocks: list, source_language: str) -> str:
    """
    Resolve "Auto" to a concrete English source-language name for remote APIs.
    Latin-script or mixed pages remain "Auto" so the backend can auto-detect.
    """
    if source_language != "Auto":
        return source_language

    dominant_script = get_dominant_page_script(blocks) or get_dominant_page_script(blocks, 0.0)
    return get_source_language_for_script(dominant_script) if dominant_script else "Auto"


def _block_area(block) -> float:
    try:
        x1, y1, x2, y2 = block.xyxy
    except (AttributeError, TypeError, ValueError):
        return 1.0
    return max(1.0, float(x2 - x1)) * max(1.0, float(y2 - y1))


def is_no_space_lang(lang_code: str | None) -> bool:
    """
    Check if the language usually does not use spaces between words.
    Includes: Chinese (zh), Japanese (ja), Thai (th).
    """
    if not lang_code:
        return False
    code = lang_code.lower()
    return any(lang in code for lang in ['zh', 'ja', 'th'])
