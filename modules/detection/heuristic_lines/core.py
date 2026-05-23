from __future__ import annotations
import math
import numpy as np

from modules.utils.textblock import TextBlock
from .geometry import _clamp_box, _expand_box, _to_box, _offset_line, _pad_line_boxes, _union_box
from .mask import _prepare_text_mask
from .direction import _fallback_direction, _sort_lines
from .skew import _detect_horizontal_lines_skew_aware
from .clustering import _detect_lines_from_mask
from .scoring import (
    _score_line_candidate, _is_large_glyph_horizontal, _is_multiline_horizontal_text,
    _is_sparse_horizontal_overfit, _detect_sparse_vertical_component_columns
)

def annotate_blocks_with_heuristic_lines(
    image: np.ndarray,
    blocks: list[TextBlock],
    source_language: str | None = None,
) -> list[TextBlock]:
    if image is None or image.size == 0 or not blocks:
        return blocks

    height, width = image.shape[:2]
    for block in blocks:
        block_source_language = source_language if source_language is not None else getattr(block, "source_lang", "")
        crop_box = _clamp_box(_expand_box(_to_box(block.xyxy), 4, 4, width, height), width, height)
        x1, y1, x2, y2 = crop_box
        if x2 <= x1 or y2 <= y1:
            block.lines = [crop_box]
            block.direction = _fallback_direction(crop_box, block_source_language)
            continue

        crop = image[y1:y2, x1:x2]
        lines, direction = _detect_lines_and_direction_in_crop(crop, block_source_language)
        image_lines = [_offset_line(line, x1, y1) for line in lines]

        block.lines = _sort_lines(image_lines, direction)
        block.direction = direction

    return blocks

def _detect_lines_in_crop(image: np.ndarray, direction_hint: str | None) -> list[list[int]]:
    if direction_hint in {"horizontal", "vertical"}:
        text_mask = _prepare_text_mask(image)
        if text_mask is None:
            height, width = image.shape[:2]
            return [[0, 0, max(0, width), max(0, height)]]
        return _detect_lines_from_mask(text_mask, direction_hint)

    lines, _ = _detect_lines_and_direction_in_crop(image)
    return lines

def _detect_lines_and_direction_in_crop(
    image: np.ndarray,
    source_language: str = "",
) -> tuple[list[list[int]], str]:
    height, width = image.shape[:2]
    if width <= 1 or height <= 1:
        box = [0, 0, max(0, width), max(0, height)]
        return [box], _fallback_direction(box, source_language)

    text_mask = _prepare_text_mask(image)
    if text_mask is None or not bool(text_mask.any()):
        box = [0, 0, width, height]
        return [box], _fallback_direction(box, source_language)

    horizontal_lines = _detect_horizontal_lines_skew_aware(text_mask)
    vertical_lines = _detect_lines_from_mask(text_mask, "vertical")

    horizontal_score = _score_line_candidate(horizontal_lines, "horizontal", text_mask)
    vertical_score = _score_line_candidate(vertical_lines, "vertical", text_mask)

    if _is_large_glyph_horizontal(text_mask, horizontal_lines, vertical_lines):
        direction = "horizontal"
    elif _is_multiline_horizontal_text(horizontal_lines, vertical_lines):
        direction = "horizontal"
    elif _is_sparse_horizontal_overfit(text_mask, horizontal_lines, vertical_lines, horizontal_score, vertical_score):
        sparse_vertical_lines = _detect_sparse_vertical_component_columns(text_mask)
        if sparse_vertical_lines:
            vertical_lines = sparse_vertical_lines
        direction = "vertical"
    elif abs(horizontal_score - vertical_score) < 0.2:
        union = _union_box(horizontal_lines + vertical_lines) or [0, 0, width, height]
        direction = _fallback_direction(union, source_language)
    else:
        direction = "vertical" if vertical_score > horizontal_score else "horizontal"

    lines = vertical_lines if direction == "vertical" else horizontal_lines
    if not lines:
        lines = [[0, 0, width, height]]
    lines = _pad_line_boxes(lines, direction, width, height)
    return lines, direction
