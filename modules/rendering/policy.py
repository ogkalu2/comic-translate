from __future__ import annotations


def is_vertical_language_code(lang_code: str | None) -> bool:
    """Return True if the language code should use vertical layout."""
    if not lang_code:
        return False
    code = str(lang_code).strip().lower().replace("_", "-")
    return code in {
        "zh",
        "zh-cn",
        "zh-tw",
        "ja",
        "chinese",
        "simplified chinese",
        "traditional chinese",
        "japanese",
    }


def is_vertical_block(blk, lang_code: str | None) -> bool:
    """Return True if this block should be rendered vertically."""
    return is_vertical_language_code(lang_code)
