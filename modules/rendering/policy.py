from __future__ import annotations


def is_vertical_language_code(lang_code: str | None) -> bool:
    """Return True if the language code should use vertical layout."""
    if not lang_code:
        return False
    code = lang_code.lower()
    return code in {"zh-cn", "zh-tw", "ja"}


def is_vertical_block(blk, lang_code: str | None) -> bool:
    """Return True if this block should be rendered vertically."""
    direction = getattr(blk, "direction", "")
    if hasattr(blk, "render_state"):
        try:
            direction = blk.render_state().direction
        except Exception:
            direction = getattr(blk, "direction", "")
    return direction == "vertical" and is_vertical_language_code(lang_code)
