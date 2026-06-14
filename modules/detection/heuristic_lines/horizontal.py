from __future__ import annotations
import numpy as np

from .geometry import _line_axis_box, _union_box
from .mask import _prepare_inverse_text_mask
from .skew import _detect_horizontal_lines_skew_aware
from .clustering import (
    _detect_lines_from_mask,
    _trim_marginal_vertical_noise_from_horizontal_lines,
)

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

    # Calculate median line height
    heights = [box[3] - box[1] + 1 for box in boxes]
    median_h = float(np.median(heights)) if heights else 0
    ratio = median_h / height if height > 0 else 0

    # If the lines are thin relative to the crop height, it's likely border noise, so collapse them.
    # Otherwise, check for vertical separation.
    if ratio >= 0.25:
        sorted_boxes = sorted(boxes, key=lambda b: (b[1] + b[3]) / 2.0)
        has_vertical_separation = False
        for i in range(len(sorted_boxes) - 1):
            b1 = sorted_boxes[i]
            b2 = sorted_boxes[i+1]
            h1 = b1[3] - b1[1] + 1
            h2 = b2[3] - b2[1] + 1
            overlap = min(b1[3], b2[3]) - max(b1[1], b2[1]) + 1
            min_h = min(h1, h2)
            if min_h > 0 and (overlap / min_h) < 0.40:
                has_vertical_separation = True
                break

        if has_vertical_separation:
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

    inverse_mask: np.ndarray | None = None

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

    if inverse_mask is None:
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
