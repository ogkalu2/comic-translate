from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from modules.utils.textblock import TextBlock


def classify_sfx_blocks(blk_list: list[TextBlock]) -> None:
    """
    Geometrically classify text_free blocks as SFX candidates.

    A block is marked is_sfx=True when ALL of:
    - text_class == 'text_free' (outside any speech bubble)
    - 3 words or fewer (SFX are short)
    - Noticeably angled (|angle| > 5°) OR aspect ratio is wide/square
      (SFX are rarely tall narrow caption boxes)

    This runs before OCR so blk.text may be empty; the glossary-based
    pass in ocr_handler will refine the classification afterwards.
    """
    for blk in blk_list:
        if blk.text_class != 'text_free':
            continue

        word_count = len(blk.text.split()) if blk.text else 0
        if word_count > 3:
            continue

        angle = getattr(blk, 'angle', 0) or 0
        is_angled = abs(angle) > 5

        if blk.xyxy is not None and len(blk.xyxy) == 4:
            x1, y1, x2, y2 = blk.xyxy
            w = max(x2 - x1, 1)
            h = max(y2 - y1, 1)
            aspect = w / h
            # Wide or square blocks are SFX-like; tall narrow ones are captions
            is_sfx_shape = aspect >= 0.6
        else:
            is_sfx_shape = True

        if is_angled or is_sfx_shape:
            blk.is_sfx = True
