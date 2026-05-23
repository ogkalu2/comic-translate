from __future__ import annotations
import math
import numpy as np

from modules.utils.textblock import TextBlock
from .geometry import _clamp_box, _expand_box, _to_box, _offset_line, _pad_line_boxes, _union_box
from .mask import _prepare_text_mask
from .direction import _fallback_direction, _sort_lines
from .skew import _detect_horizontal_lines_skew_aware
from .clustering import _detect_lines_from_mask, _trim_marginal_vertical_noise_from_horizontal_lines
from .scoring import (
    _score_line_candidate, _is_large_glyph_horizontal, _is_multiline_horizontal_text,
    _is_fragmented_rotated_horizontal_text, _is_sparse_horizontal_overfit,
    _detect_sparse_vertical_component_columns
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

    from .skew import _filter_noise_lines
    horizontal_lines = _detect_horizontal_lines_skew_aware(text_mask)
    vertical_lines = _filter_noise_lines(_detect_lines_from_mask(text_mask, "vertical"), "vertical")

    horizontal_score = _score_line_candidate(horizontal_lines, "horizontal", text_mask)
    vertical_score = _score_line_candidate(vertical_lines, "vertical", text_mask)

    if _is_large_glyph_horizontal(text_mask, horizontal_lines, vertical_lines):
        direction = "horizontal"
    elif _is_multiline_horizontal_text(horizontal_lines, vertical_lines):
        direction = "horizontal"
    elif _is_fragmented_rotated_horizontal_text(text_mask, horizontal_lines, vertical_lines):
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

    mask_was_split = False
    if direction == "horizontal":
        from .geometry import _is_polygon_line
        horizontal_lines = _detect_horizontal_lines_skew_aware(text_mask)
        has_slanted_lines = any(_is_polygon_line(line) for line in horizontal_lines)
        if has_slanted_lines:
            lines = horizontal_lines
        else:
            from .mask import _split_mask_by_tall_vertical_columns
            sub_masks = _split_mask_by_tall_vertical_columns(text_mask)
            if len(sub_masks) > 1:
                lines = []
                for sub_mask in sub_masks:
                    sub_lines = _detect_horizontal_lines_skew_aware(sub_mask)
                    sub_lines = [l for l in sub_lines if l != [0, 0, width, height]]
                    lines.extend(sub_lines)
                mask_was_split = True
            else:
                lines = horizontal_lines
        lines = _trim_marginal_vertical_noise_from_horizontal_lines(lines, text_mask, vertical_lines)
    else:
        lines = vertical_lines

    if not lines:
        lines = [[0, 0, width, height]]
    lines = _pad_line_boxes(lines, direction, width, height)

    # Filter out wrong-direction noise columns/rows (e.g. vertical noise columns in a horizontal block)
    if not mask_was_split:
        try:
            import imkit as imk
            from .geometry import _line_axis_box
            num_labels, labels, stats, _ = imk.connected_components_with_stats(
                text_mask.astype(np.uint8),
                connectivity=8,
            )
            valid_widths = []
            valid_heights = []
            for label in range(1, num_labels):
                _, _, comp_width, comp_height, area = [int(v) for v in stats[label]]
                if area >= 8:
                    valid_widths.append(comp_width)
                    valid_heights.append(comp_height)
            median_w = float(np.median(valid_widths)) if valid_widths else 12.0
            median_h = float(np.median(valid_heights)) if valid_heights else 12.0

            filtered_lines = []
            for line in lines:
                x1, y1, x2, y2 = _line_axis_box(line)
                line_w = max(1, x2 - x1 + 1)
                line_h = max(1, y2 - y1 + 1)
                
                if direction == "horizontal":
                    if line_h > line_w and line_h > 2.0 * median_h:
                        continue
                else:
                    if line_w > line_h and line_w > 2.0 * median_w:
                        continue
                filtered_lines.append(line)
            if filtered_lines:
                lines = filtered_lines
        except Exception as e:
            print(f"Failed to filter wrong-direction noise lines: {e}")

    return lines, direction
