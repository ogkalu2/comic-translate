from __future__ import annotations
import math
import numpy as np
import imkit as imk

from .geometry import _line_axis_box, _clamp_box, _is_polygon_line
from .clustering import _cluster_components_by_y, _component_boxes, _components_to_box
from .mask import _MaskStats, _sum_box_pixels

def _score_line_candidate(
    lines: list[list[int]],
    direction: str,
    text_mask: np.ndarray,
    mask_stats: _MaskStats | None = None,
) -> float:
    if not lines:
        return -1_000_000.0

    total_text_pixels = mask_stats.total_pixels if mask_stats is not None else int(text_mask.sum())
    if total_text_pixels <= 0:
        return -1_000_000.0

    covered_pixels = 0
    total_area = 0.0
    shape_scores: list[float] = []
    for line in lines:
        line_pixels, line_area, line_width, line_height = _line_coverage_metrics(line, text_mask, mask_stats=mask_stats)
        if line_area <= 0:
            continue

        covered_pixels += line_pixels
        total_area += line_area

        ratio = line_width / line_height if direction == "horizontal" else line_height / line_width
        shape_scores.append(math.tanh(math.log(max(ratio, 1e-6))))

    if total_area <= 0 or not shape_scores:
        return -1_000_000.0

    coverage = covered_pixels / total_text_pixels
    density = covered_pixels / total_area
    shape_score = float(np.mean(shape_scores))

    fragmentation_penalty = 0.08 * max(0, len(lines) - 1)

    return coverage * 1.4 + density * 0.8 + shape_score * 1.2 - fragmentation_penalty

def _line_coverage_metrics(
    line,
    text_mask: np.ndarray,
    mask_stats: _MaskStats | None = None,
) -> tuple[int, float, float, float]:
    if _is_polygon_line(line):
        points = np.asarray(line, dtype=float)[:4]
        edge_x = points[1] - points[0]
        edge_y = points[3] - points[0]
        line_width = max(1.0, float(np.linalg.norm(edge_x)))
        line_height = max(1.0, float(np.linalg.norm(edge_y)))
        axis_box = _clamp_box(_line_axis_box(points), text_mask.shape[1], text_mask.shape[0])
        x1, y1, x2, y2 = axis_box
        if x2 < x1 or y2 < y1:
            return 0, 0.0, line_width, line_height

        region = text_mask[y1:y2 + 1, x1:x2 + 1]
        ys, xs = np.where(region)
        if xs.size == 0:
            return 0, line_width * line_height, line_width, line_height

        ink_points = np.empty((xs.size, 2), dtype=np.float64)
        ink_points[:, 0] = xs + x1
        ink_points[:, 1] = ys + y1
        delta = ink_points - points[0]
        unit_x = edge_x / line_width
        unit_y = edge_y / line_height
        local_x = delta @ unit_x
        local_y = delta @ unit_y
        inside = (
            (local_x >= -0.5)
            & (local_x <= line_width + 0.5)
            & (local_y >= -0.5)
            & (local_y <= line_height + 0.5)
        )
        return int(inside.sum()), line_width * line_height, line_width, line_height

    x1, y1, x2, y2 = _clamp_box(_line_axis_box(line), text_mask.shape[1], text_mask.shape[0])
    if x2 < x1 or y2 < y1:
        return 0, 0.0, 1.0, 1.0

    line_width = float(max(1, x2 - x1 + 1))
    line_height = float(max(1, y2 - y1 + 1))
    if mask_stats is not None:
        pixels = _sum_box_pixels(mask_stats.integral_image, x1, y1, x2, y2)
    else:
        pixels = int(text_mask[y1:y2 + 1, x1:x2 + 1].sum())
    return pixels, line_width * line_height, line_width, line_height

def _is_large_glyph_horizontal(
    text_mask: np.ndarray,
    horizontal_lines: list[list[int]],
    vertical_lines: list[list[int]],
    mask_stats: _MaskStats | None = None,
) -> bool:
    union = _union_box_local(horizontal_lines + vertical_lines)
    if union is None:
        return False

    width = max(1, union[2] - union[0] + 1)
    height = max(1, union[3] - union[1] + 1)
    if width < height * 0.9 or len(horizontal_lines) > 2 or len(vertical_lines) > 4:
        return False

    components = []
    if mask_stats is not None:
        for component in mask_stats.component_boxes:
            components.append((
                int(component["x1"]),
                int(component["y1"]),
                int(component["width"]),
                int(component["height"]),
                int(component["area"]),
                np.asarray([component["cx"], component["cy"]], dtype=float),
            ))
    else:
        num_labels, _, stats, centroids = imk.connected_components_with_stats(
            text_mask.astype(np.uint8),
            connectivity=8,
        )
        for label in range(1, num_labels):
            x1, y1, comp_width, comp_height, area = [int(v) for v in stats[label]]
            if area < 20:
                continue
            components.append((x1, y1, comp_width, comp_height, area, centroids[label]))

    if components:
        max_area = max(component[4] for component in components)
        components = [component for component in components if component[4] >= max(20, max_area * 0.15)]

    if not 1 <= len(components) <= 6:
        return False

    centers_y = np.array([float(component[5][1]) for component in components], dtype=float)
    median_height = float(np.median([component[3] for component in components]))
    return float(centers_y.max() - centers_y.min()) <= max(12.0, median_height * 0.8)

def _union_box_local(lines: list[list[int]]) -> list[int] | None:
    if not lines:
        return None
    boxes = [_line_axis_box(line) for line in lines]
    xs1 = [box[0] for box in boxes]
    ys1 = [box[1] for box in boxes]
    xs2 = [box[2] for box in boxes]
    ys2 = [box[3] for box in boxes]
    return [min(xs1), min(ys1), max(xs2), max(ys2)]

def _is_multiline_horizontal_text(horizontal_lines: list[list[int]], vertical_lines: list[list[int]]) -> bool:
    if len(horizontal_lines) < 3 or len(vertical_lines) != 1:
        return False

    boxes = [_line_axis_box(line) for line in horizontal_lines]
    widths = np.array([box[2] - box[0] + 1 for box in boxes], dtype=float)
    heights = np.array([box[3] - box[1] + 1 for box in boxes], dtype=float)
    if widths.size == 0 or heights.size == 0:
        return False

    ratios = widths / np.maximum(1.0, heights)
    row_like_count = int((ratios >= 1.8).sum())
    if row_like_count < max(3, int(math.ceil(len(horizontal_lines) * 0.65))):
        return False

    union = _union_box_local(horizontal_lines)
    if union is None:
        return False

    median_height = float(np.median(heights))
    median_width = float(np.median(widths))
    union_width = max(1, union[2] - union[0] + 1)
    union_height = max(1, union[3] - union[1] + 1)
    if union_height < median_height * 3.0 or median_width < max(16.0, union_width * 0.35):
        return False

    centers_y = sorted((box[1] + box[3]) / 2.0 for box in boxes)
    if len(centers_y) >= 2 and float(np.median(np.diff(centers_y))) < median_height * 0.75:
        return False

    vertical_box = _line_axis_box(vertical_lines[0])
    vertical_width = max(1, vertical_box[2] - vertical_box[0] + 1)
    vertical_height = max(1, vertical_box[3] - vertical_box[1] + 1)
    return vertical_height > vertical_width * 1.2

def _is_fragmented_rotated_horizontal_text(
    text_mask: np.ndarray,
    horizontal_lines: list[list[int]],
    vertical_lines: list[list[int]],
    component_boxes: list[dict[str, float]] | None = None,
) -> bool:
    if len(horizontal_lines) < 5 or len(vertical_lines) < 2:
        return False

    height, width = text_mask.shape[:2]
    vertical_boxes = [_line_axis_box(line) for line in vertical_lines]
    broad_verticals = [
        box for box in vertical_boxes
        if (box[2] - box[0] + 1) >= width * 0.55 and (box[3] - box[1] + 1) >= height * 0.65
    ]
    if len(broad_verticals) != 1:
        return False

    broad_box = broad_verticals[0]
    broad_width = max(1, broad_box[2] - broad_box[0] + 1)
    for box in vertical_boxes:
        if box == broad_box:
            continue
        box_width = max(1, box[2] - box[0] + 1)
        if box_width > max(14, int(round(broad_width * 0.14))):
            return False

    horizontal_boxes = [_line_axis_box(line) for line in horizontal_lines]
    row_like_count = 0
    for box in horizontal_boxes:
        line_width = max(1, box[2] - box[0] + 1)
        line_height = max(1, box[3] - box[1] + 1)
        if line_width >= line_height * 1.8 and line_width >= width * 0.25:
            row_like_count += 1
    if row_like_count < 4:
        return False

    components = _component_boxes(text_mask)
    if len(components) < 8:
        return False

    median_height = float(np.median([component["height"] for component in components]))
    median_width = float(np.median([component["width"] for component in components]))
    component_rows = _cluster_components_by_y(components, median_height)
    substantial_rows = 0
    for row in component_rows:
        box = _components_to_box(row)
        if box is None:
            continue
        row_width = max(1, box[2] - box[0] + 1)
        if len(row) >= 2 and row_width >= max(width * 0.25, median_width * 4.0):
            substantial_rows += 1

    return substantial_rows >= 4

def _is_sparse_horizontal_overfit(
    text_mask: np.ndarray,
    horizontal_lines: list[list[int]],
    vertical_lines: list[list[int]],
    horizontal_score: float,
    vertical_score: float,
    mask_stats: _MaskStats | None = None,
) -> bool:
    if len(horizontal_lines) < 5 or len(vertical_lines) < len(horizontal_lines):
        return False

    total_pixels = mask_stats.total_pixels if mask_stats is not None else int(text_mask.sum())
    mask_density = total_pixels / max(1, text_mask.shape[0] * text_mask.shape[1])
    if mask_density >= 0.06 or vertical_score < horizontal_score - 0.12:
        return False

    densities: list[float] = []
    for line in horizontal_lines:
        pixels, area, _, _ = _line_coverage_metrics(line, text_mask, mask_stats=mask_stats)
        if area > 0:
            densities.append(pixels / area)

    return bool(densities) and float(np.median(densities)) < 0.09

def _detect_sparse_vertical_component_columns(
    text_mask: np.ndarray,
    component_boxes: list[dict[str, float]] | None = None,
) -> list[list[int]]:
    components = component_boxes if component_boxes is not None else _component_boxes(text_mask)
    if len(components) < 2:
        return []

    areas = np.array([component["area"] for component in components], dtype=float)
    median_area = float(np.median(areas))
    components = [component for component in components if component["area"] >= max(20.0, median_area * 0.35)]
    if len(components) < 2:
        return []

    median_width = float(np.median([component["width"] for component in components]))
    center_gap = max(12.0, median_width * 1.25)
    columns: list[list[dict[str, float]]] = []
    for component in sorted(components, key=lambda item: item["cx"]):
        if not columns:
            columns.append([component])
            continue

        column_center = float(np.mean([item["cx"] for item in columns[-1]]))
        if component["cx"] - column_center > center_gap:
            columns.append([component])
        else:
            columns[-1].append(component)

    boxes = [_components_to_box(column) for column in columns]
    return [box for box in boxes if box is not None]
