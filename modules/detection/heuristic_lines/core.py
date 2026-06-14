from __future__ import annotations
import numpy as np

from modules.utils.textblock import TextBlock
from .geometry import _clamp_box, _expand_box, _to_box, _offset_line, _pad_line_boxes, _union_box, _line_axis_box
from .mask import _compute_mask_stats, _prepare_text_mask
from .direction import _fallback_direction, _sort_lines
from .skew import _detect_horizontal_lines_skew_aware, _filter_noise_lines
from .clustering import (
    _detect_lines_from_mask,
    _filter_marginal_horizontal_artifacts,
    _merge_small_horizontal_fragments,
    _trim_marginal_vertical_noise_from_horizontal_lines,
)
from .scoring import (
    _score_line_candidate, _is_large_glyph_horizontal, _is_multiline_horizontal_text,
    _is_fragmented_rotated_horizontal_text, _is_sparse_horizontal_overfit,
    _detect_sparse_vertical_component_columns, _looks_like_structured_vertical_columns,
)
from .horizontal import (
    _collapse_edge_spanning_horizontal_fragments,
    _replace_low_density_line_with_inverse_mask,
)
from .vertical import (
    _align_vertical_lines_to_detector_block,
    _trim_disconnected_vertical_line_tails,
    _drop_nested_vertical_line_duplicates,
    _widen_skinny_vertical_lines_by_spacing,
    _split_tall_vertical_lines_on_valleys,
    _merge_fragmented_top_edge_vertical_lines,
    _repair_fragmented_vertical_blocks_with_raw_support,
)
from .column_routing import (
    _should_use_component_vertical_columns,
    _should_add_one_component_vertical_column,
    _structured_columns_should_override_horizontal,
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
        if direction == "vertical":
            image_lines = _align_vertical_lines_to_detector_block(image_lines, _to_box(block.xyxy))

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
    mask_stats = _compute_mask_stats(text_mask)

    horizontal_lines = _detect_horizontal_lines_skew_aware(text_mask)
    vertical_lines = _filter_noise_lines(_detect_lines_from_mask(text_mask, "vertical"), "vertical")
    raw_vertical_lines = [list(_line_axis_box(line)) for line in vertical_lines]
    component_vertical_lines = _detect_sparse_vertical_component_columns(text_mask, component_boxes=mask_stats.component_boxes)

    horizontal_score = _score_line_candidate(horizontal_lines, "horizontal", text_mask, mask_stats=mask_stats)
    vertical_score = _score_line_candidate(vertical_lines, "vertical", text_mask, mask_stats=mask_stats)
    has_structured_vertical_columns = _looks_like_structured_vertical_columns(text_mask, component_vertical_lines)

    if _is_large_glyph_horizontal(text_mask, horizontal_lines, vertical_lines, mask_stats=mask_stats):
        direction = "horizontal"
    elif _is_multiline_horizontal_text(horizontal_lines, vertical_lines):
        direction = "horizontal"
    elif has_structured_vertical_columns and _structured_columns_should_override_horizontal(
        text_mask,
        horizontal_lines,
        vertical_lines,
        component_vertical_lines,
        horizontal_score,
        vertical_score,
    ):
        if _should_use_component_vertical_columns(text_mask, vertical_lines, component_vertical_lines):
            vertical_lines = component_vertical_lines
        direction = "vertical"
    elif _is_fragmented_rotated_horizontal_text(text_mask, horizontal_lines, vertical_lines, component_boxes=mask_stats.component_boxes):
        direction = "horizontal"
    elif _is_sparse_horizontal_overfit(text_mask, horizontal_lines, vertical_lines, horizontal_score, vertical_score, mask_stats=mask_stats):
        if component_vertical_lines:
            vertical_lines = component_vertical_lines
        direction = "vertical"
    elif abs(horizontal_score - vertical_score) < 0.2:
        union = _union_box(horizontal_lines + vertical_lines) or [0, 0, width, height]
        direction = _fallback_direction(union, source_language)
    else:
        direction = "vertical" if vertical_score > horizontal_score else "horizontal"

    mask_was_split = False
    if direction == "horizontal":
        from .geometry import _is_polygon_line
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
        lines = _trim_marginal_vertical_noise_from_horizontal_lines(
            lines,
            text_mask,
            vertical_lines,
            component_boxes=mask_stats.component_boxes,
            integral_image=mask_stats.integral_image,
        )
        lines = _collapse_edge_spanning_horizontal_fragments(lines, text_mask, vertical_lines)
        lines, text_mask = _replace_low_density_line_with_inverse_mask(image, lines, text_mask)
        lines = _merge_small_horizontal_fragments(lines)
        lines = _filter_marginal_horizontal_artifacts(lines, text_mask)
    else:
        if _should_use_component_vertical_columns(text_mask, vertical_lines, component_vertical_lines) or _should_add_one_component_vertical_column(
            text_mask,
            vertical_lines,
            component_vertical_lines,
            horizontal_score,
            vertical_score,
        ):
            vertical_lines = component_vertical_lines
        lines = _trim_disconnected_vertical_line_tails(vertical_lines, text_mask, mask_stats)
        lines = _drop_nested_vertical_line_duplicates(lines)

    if not lines:
        lines = [[0, 0, width, height]]
    lines = _pad_line_boxes(lines, direction, width, height)
    if direction == "vertical":
        lines = _widen_skinny_vertical_lines_by_spacing(lines, width, mask_stats)
        lines = _split_tall_vertical_lines_on_valleys(lines, text_mask, mask_stats)
        lines = _merge_fragmented_top_edge_vertical_lines(lines, text_mask, mask_stats)
        lines = _repair_fragmented_vertical_blocks_with_raw_support(lines, raw_vertical_lines, text_mask, mask_stats)

    # Filter out wrong-direction noise columns/rows (e.g. vertical noise columns in a horizontal block)
    if not mask_was_split:
        try:
            final_mask_stats = mask_stats if text_mask is mask_stats.mask else _compute_mask_stats(text_mask)
            median_w = final_mask_stats.median_w
            median_h = final_mask_stats.median_h

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
