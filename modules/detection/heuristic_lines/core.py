from __future__ import annotations
import math
import numpy as np

from modules.utils.textblock import TextBlock
from .geometry import _clamp_box, _expand_box, _to_box, _offset_line, _pad_line_boxes, _union_box, _line_axis_box
from .mask import _prepare_inverse_text_mask, _prepare_text_mask
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
    component_vertical_lines = _detect_sparse_vertical_component_columns(text_mask)

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
        lines = _collapse_edge_spanning_horizontal_fragments(lines, text_mask, vertical_lines)
        lines, text_mask = _replace_low_density_line_with_inverse_mask(image, lines, text_mask)
    else:
        if _should_use_component_vertical_columns(text_mask, vertical_lines, component_vertical_lines):
            vertical_lines = component_vertical_lines
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

def _collapse_edge_spanning_horizontal_fragments(
    lines: list[list[int]],
    text_mask: np.ndarray,
    vertical_lines: list[list[int]],
) -> list[list[int]]:
    if len(lines) <= 1:
        return lines
    if len(lines) > 4 or len(vertical_lines) < 2:
        return lines

    height, width = text_mask.shape[:2]
    if width <= 0 or height <= 0:
        return lines

    boxes = [_line_axis_box(line) for line in lines]
    edge_margin = max(2, int(round(height * 0.04)))
    min_edge_width = max(12, int(round(width * 0.25)))

    def is_wide_top_edge(box: list[int]) -> bool:
        return box[1] <= edge_margin and (box[2] - box[0] + 1) >= min_edge_width

    def is_wide_bottom_edge(box: list[int]) -> bool:
        return box[3] >= height - 1 - edge_margin and (box[2] - box[0] + 1) >= min_edge_width

    has_top_edge = any(is_wide_top_edge(box) for box in boxes)
    has_bottom_edge = any(is_wide_bottom_edge(box) for box in boxes)
    if not has_top_edge or not has_bottom_edge:
        return lines

    union = _union_box(lines)
    if union is None:
        return lines

    union_width = max(1, union[2] - union[0] + 1)
    union_height = max(1, union[3] - union[1] + 1)
    if union_width < width * 0.55 or union_height < height * 0.70:
        return lines

    return [union]

def _replace_low_density_line_with_inverse_mask(
    image: np.ndarray,
    lines: list[list[int]],
    text_mask: np.ndarray,
) -> tuple[list[list[int]], np.ndarray]:
    if len(lines) != 1:
        return lines, text_mask

    height, width = text_mask.shape[:2]
    box = _line_axis_box(lines[0])
    line_width = max(1, box[2] - box[0] + 1)
    line_height = max(1, box[3] - box[1] + 1)
    current_density = _line_box_density(text_mask, box)

    if line_width >= width * 0.55 and line_height >= height * 0.60 and current_density < 0.08:
        inverse_mask = _prepare_inverse_text_mask(image)
        if inverse_mask is not None and bool(inverse_mask.any()):
            expanded_title_line = _large_inverse_component_title_line(inverse_mask, box)
            if expanded_title_line is not None:
                return [expanded_title_line], inverse_mask

    if line_width < width * 0.65 or line_height < height * 0.65:
        return lines, text_mask

    if current_density >= 0.08:
        return lines, text_mask

    inverse_mask = _prepare_inverse_text_mask(image)
    if inverse_mask is None or not bool(inverse_mask.any()):
        return lines, text_mask

    inverse_lines = _detect_horizontal_lines_skew_aware(inverse_mask)
    from .skew import _filter_noise_lines
    inverse_vertical_lines = _filter_noise_lines(_detect_lines_from_mask(inverse_mask, "vertical"), "vertical")
    inverse_lines = _trim_marginal_vertical_noise_from_horizontal_lines(
        inverse_lines,
        inverse_mask,
        inverse_vertical_lines,
    )
    if len(inverse_lines) != 1:
        return lines, text_mask

    inverse_box = _line_axis_box(inverse_lines[0])
    inverse_height = max(1, inverse_box[3] - inverse_box[1] + 1)
    inverse_density = _line_box_density(inverse_mask, inverse_box)
    if inverse_height >= line_height * 0.80:
        return lines, text_mask
    if inverse_density < max(0.12, current_density * 2.0):
        return lines, text_mask

    return inverse_lines, inverse_mask

def _large_inverse_component_title_line(inverse_mask: np.ndarray, current_box: list[int]) -> list[int] | None:
    import imkit as imk

    height, width = inverse_mask.shape[:2]
    num_labels, _, stats, _ = imk.connected_components_with_stats(
        inverse_mask.astype(np.uint8),
        connectivity=8,
    )
    if num_labels <= 1:
        return None

    min_area = max(900, int(round(inverse_mask.size * 0.0018)))
    min_width = max(35, int(round(width * 0.025)))
    min_height = max(35, int(round(height * 0.10)))
    selected: list[list[int]] = []
    for label in range(1, num_labels):
        x1, y1, comp_width, comp_height, area = [int(v) for v in stats[label]]
        if area < min_area:
            continue
        if comp_width < min_width and comp_height < min_height:
            continue

        x2 = x1 + comp_width - 1
        y2 = y1 + comp_height - 1
        density = area / max(1, comp_width * comp_height)

        # Top-edge hatching can survive inverse cleanup in title banners.
        if y1 <= int(round(height * 0.06)) and comp_height >= int(round(height * 0.28)) and density < 0.36:
            continue
        selected.append([x1, y1, x2, y2])

    if len(selected) < 4:
        return None

    union = _union_box(selected)
    if union is None:
        return None

    union_width = max(1, union[2] - union[0] + 1)
    union_height = max(1, union[3] - union[1] + 1)
    current_width = max(1, current_box[2] - current_box[0] + 1)
    if union_width < max(width * 0.55, current_width * 1.15):
        return None
    if union_height < height * 0.35:
        return None
    if union[1] <= 4 and union[3] >= height - 5:
        return None

    return union

def _line_box_density(text_mask: np.ndarray, box: list[int]) -> float:
    height, width = text_mask.shape[:2]
    x1 = max(0, min(width - 1, int(box[0])))
    y1 = max(0, min(height - 1, int(box[1])))
    x2 = max(0, min(width - 1, int(box[2])))
    y2 = max(0, min(height - 1, int(box[3])))
    if x2 < x1 or y2 < y1:
        return 0.0
    area = max(1, (x2 - x1 + 1) * (y2 - y1 + 1))
    return float(text_mask[y1 : y2 + 1, x1 : x2 + 1].sum()) / float(area)

def _should_use_component_vertical_columns(
    text_mask: np.ndarray,
    vertical_lines: list[list[int]],
    component_vertical_lines: list[list[int]],
) -> bool:
    if len(vertical_lines) > 2:
        return False
    if len(component_vertical_lines) <= len(vertical_lines) or len(component_vertical_lines) > 4:
        return False

    height, width = text_mask.shape[:2]
    raw_boxes = [_line_axis_box(line) for line in vertical_lines]
    component_boxes = [_line_axis_box(line) for line in component_vertical_lines]

    has_merged_raw_column = any((box[2] - box[0] + 1) >= width * 0.45 for box in raw_boxes)
    if not has_merged_raw_column:
        return False

    verticalish_components = 0
    for box in component_boxes:
        box_width = max(1, box[2] - box[0] + 1)
        box_height = max(1, box[3] - box[1] + 1)
        if box_height >= max(height * 0.25, box_width * 1.8):
            verticalish_components += 1

    return verticalish_components >= max(2, len(component_boxes) - 1)
