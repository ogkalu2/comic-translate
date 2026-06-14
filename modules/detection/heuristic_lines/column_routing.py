from __future__ import annotations
import numpy as np

from .geometry import _line_axis_box, _union_box
from .scoring import _looks_like_structured_vertical_columns

def _should_use_component_vertical_columns(
    text_mask: np.ndarray,
    vertical_lines: list[list[int]],
    component_vertical_lines: list[list[int]],
) -> bool:
    if _looks_like_single_component_vertical_column(text_mask, vertical_lines, component_vertical_lines):
        return True

    if not _looks_like_structured_vertical_columns(text_mask, component_vertical_lines):
        return False

    height, width = text_mask.shape[:2]
    raw_boxes = [_line_axis_box(line) for line in vertical_lines]
    component_boxes = [_line_axis_box(line) for line in component_vertical_lines]
    if not raw_boxes or not component_boxes:
        return False

    has_merged_raw_column = any((box[2] - box[0] + 1) >= width * 0.45 for box in raw_boxes)
    if len(vertical_lines) <= 2 and len(component_vertical_lines) > len(vertical_lines) and len(component_vertical_lines) <= 6:
        if not has_merged_raw_column:
            return False
        if len(component_vertical_lines) < 4 and _component_columns_have_strong_overlap(component_boxes):
            return False
        return True

    if len(component_vertical_lines) < len(vertical_lines):
        return _has_skinny_raw_vertical_artifacts(raw_boxes)

    if len(component_vertical_lines) == len(vertical_lines):
        return False

    if len(component_vertical_lines) > len(vertical_lines):
        if len(component_vertical_lines) > min(6, len(vertical_lines) + 1):
            return False
        if not has_merged_raw_column:
            return False

    if len(component_vertical_lines) <= len(vertical_lines) or len(component_vertical_lines) > 6:
        return False

    if not has_merged_raw_column:
        return False

    verticalish_components = 0
    for box in component_boxes:
        box_width = max(1, box[2] - box[0] + 1)
        box_height = max(1, box[3] - box[1] + 1)
        if box_height >= max(height * 0.25, box_width * 1.8):
            verticalish_components += 1

    return verticalish_components >= max(2, len(component_boxes) - 1)

def _has_skinny_raw_vertical_artifacts(raw_boxes: list[list[int]]) -> bool:
    if len(raw_boxes) < 2:
        return False

    widths = np.array([max(1, box[2] - box[0] + 1) for box in raw_boxes], dtype=float)
    heights = np.array([max(1, box[3] - box[1] + 1) for box in raw_boxes], dtype=float)
    median_width = float(np.median(widths)) if widths.size else 1.0
    median_height = float(np.median(heights)) if heights.size else 1.0
    skinny_limit = max(4.0, median_width * 0.25)
    tall_limit = max(40.0, median_height * 0.25)
    return bool(((widths <= skinny_limit) & (heights >= tall_limit)).any())

def _should_add_one_component_vertical_column(
    text_mask: np.ndarray,
    vertical_lines: list[list[int]],
    component_vertical_lines: list[list[int]],
    horizontal_score: float,
    vertical_score: float,
) -> bool:
    if len(component_vertical_lines) != len(vertical_lines) + 1:
        return False
    if len(component_vertical_lines) > 5:
        return False
    if horizontal_score >= 0.0 or vertical_score < horizontal_score + 1.5:
        return False
    if not _looks_like_structured_vertical_columns(text_mask, component_vertical_lines):
        return False

    component_boxes = [_line_axis_box(line) for line in component_vertical_lines]
    return not _component_columns_have_strong_overlap(component_boxes)

def _component_columns_have_strong_overlap(component_boxes: list[list[int]]) -> bool:
    if len(component_boxes) < 2:
        return False

    boxes = sorted(component_boxes, key=lambda box: box[0])
    for left, right in zip(boxes, boxes[1:]):
        overlap = min(left[2], right[2]) - max(left[0], right[0]) + 1
        if overlap <= 0:
            continue
        min_width = min(left[2] - left[0] + 1, right[2] - right[0] + 1)
        if overlap >= min_width * 0.55:
            return True
    return False

def _looks_like_single_component_vertical_column(
    text_mask: np.ndarray,
    vertical_lines: list[list[int]],
    component_vertical_lines: list[list[int]],
) -> bool:
    if len(component_vertical_lines) != 1 or len(vertical_lines) <= 1:
        return False

    component_box = _line_axis_box(component_vertical_lines[0])
    component_width = max(1, component_box[2] - component_box[0] + 1)
    component_height = max(1, component_box[3] - component_box[1] + 1)
    if component_height < max(text_mask.shape[0] * 0.35, component_width * 3.0):
        return False

    raw_union = _union_box(vertical_lines)
    if raw_union is None:
        return False

    raw_width = max(1, raw_union[2] - raw_union[0] + 1)
    raw_height = max(1, raw_union[3] - raw_union[1] + 1)
    raw_boxes = sorted((_line_axis_box(line) for line in vertical_lines), key=lambda box: box[0])
    raw_widths = np.array([max(1, box[2] - box[0] + 1) for box in raw_boxes], dtype=float)
    median_raw_width = float(np.median(raw_widths)) if raw_widths.size else 1.0
    max_gap = 0
    for left, right in zip(raw_boxes, raw_boxes[1:]):
        max_gap = max(max_gap, right[0] - left[2] - 1)
    if max_gap > max(6.0, median_raw_width * 0.35):
        return False

    overlap_x = min(component_box[2], raw_union[2]) - max(component_box[0], raw_union[0]) + 1
    overlap_y = min(component_box[3], raw_union[3]) - max(component_box[1], raw_union[1]) + 1
    return overlap_x >= raw_width * 0.70 and overlap_y >= raw_height * 0.85

def _structured_columns_should_override_horizontal(
    text_mask: np.ndarray,
    horizontal_lines: list[list[int]],
    vertical_lines: list[list[int]],
    component_vertical_lines: list[list[int]],
    horizontal_score: float,
    vertical_score: float,
) -> bool:
    if len(component_vertical_lines) < 2:
        return False

    height, width = text_mask.shape[:2]
    component_boxes = [_line_axis_box(line) for line in component_vertical_lines]
    component_heights = np.array([max(1, box[3] - box[1] + 1) for box in component_boxes], dtype=float)
    component_widths = np.array([max(1, box[2] - box[0] + 1) for box in component_boxes], dtype=float)

    if horizontal_score > 1.25 and vertical_score < horizontal_score + 1.0:
        return False

    if vertical_score >= horizontal_score + 0.50:
        return True

    tall_thresholds = np.maximum(height * 0.28, component_widths * 2.0)
    tall_columns = int((component_heights >= tall_thresholds).sum())
    if tall_columns < max(2, len(component_boxes) - 1):
        return False

    raw_vertical_boxes = [_line_axis_box(line) for line in vertical_lines]
    has_broad_raw_column = any(
        (box[2] - box[0] + 1) >= width * 0.45 and (box[3] - box[1] + 1) >= height * 0.55
        for box in raw_vertical_boxes
    )
    if not has_broad_raw_column and len(vertical_lines) < max(2, len(component_vertical_lines) // 2):
        return False

    if len(horizontal_lines) >= len(component_vertical_lines) * 2:
        return True

    return vertical_score >= horizontal_score + 0.50
