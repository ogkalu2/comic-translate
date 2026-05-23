from __future__ import annotations
import math
import numpy as np

from .geometry import _is_polygon_line, _line_axis_box
from .scoring import _score_line_candidate
from .clustering import _detect_lines_from_mask

def _detect_horizontal_lines_skew_aware(text_mask: np.ndarray) -> list[list[int]]:
    base_lines = _detect_lines_from_mask(text_mask, "horizontal")
    best_lines = base_lines
    base_score = _score_line_candidate(base_lines, "horizontal", text_mask)
    best_score = base_score

    for angle in range(-36, 37, 3):
        if angle == 0:
            continue
        candidate = _detect_horizontal_lines_at_angle(text_mask, angle)
        if len(candidate) > max(len(base_lines) + 2, int(math.ceil(len(base_lines) * 1.6))):
            continue
        if not _is_line_like_horizontal_quad_set(candidate):
            continue
        score = _score_line_candidate(candidate, "horizontal", text_mask)
        if (
            len(base_lines) >= 4
            and len(candidate) < len(base_lines) - 1
            and score < base_score + 0.35
            and not _has_reasonable_reduced_skew_thickness(base_lines, candidate)
        ):
            continue
        angle_bonus = min(0.12, abs(angle) * 0.006)
        line_count_penalty = 0.04 * max(0, len(candidate) - len(base_lines))
        adjusted_score = score + angle_bonus - line_count_penalty
        if score >= base_score - 0.12 and adjusted_score > best_score + 0.02:
            best_score = adjusted_score
            best_lines = candidate
    return best_lines

def _detect_horizontal_lines_at_angle(text_mask: np.ndarray, angle_degrees: float) -> list[list[int]]:
    height, width = text_mask.shape[:2]
    ys, xs = np.where(text_mask)
    if xs.size == 0 or ys.size == 0:
        return [[0, 0, width, height]]

    center_x = (width - 1) / 2.0
    center_y = (height - 1) / 2.0
    angle = math.radians(angle_degrees)
    sin_a = math.sin(angle)
    cos_a = math.cos(angle)
    projected_y = -sin_a * (xs - center_x) + cos_a * (ys - center_y)

    min_projection = int(math.floor(float(projected_y.min())))
    max_projection = int(math.ceil(float(projected_y.max())))
    bins = np.rint(projected_y - min_projection).astype(np.int32)
    counts = np.bincount(bins, minlength=max_projection - min_projection + 2)
    tolerance = max(1, int(width * 0.02))

    spans: list[tuple[int, int]] = []
    start = -1
    for index, count in enumerate(counts):
        if int(count) > tolerance:
            if start == -1:
                start = index
        elif start != -1:
            spans.append((start, index))
            start = -1
    if start != -1:
        spans.append((start, len(counts)))

    boxes: list[list[int]] = []
    for span_start, span_end in spans:
        selected = (bins >= span_start) & (bins < span_end)
        if not bool(selected.any()):
            continue
        line_xs = xs[selected]
        line_ys = ys[selected]
        line_projected_x = cos_a * (line_xs - center_x) + sin_a * (line_ys - center_y)
        line_projected_y = projected_y[selected]
        min_x = float(line_projected_x.min())
        max_x = float(line_projected_x.max())
        min_y = float(line_projected_y.min())
        max_y = float(line_projected_y.max())
        if (max_x - min_x) < 4 and (max_y - min_y) < 4:
            continue
        boxes.append(_quad_from_rotated_rect(min_x, min_y, max_x, max_y, center_x, center_y, sin_a, cos_a, width, height))

    return boxes or [[0, 0, width, height]]

def _quad_from_rotated_rect(
    min_x: float,
    min_y: float,
    max_x: float,
    max_y: float,
    center_x: float,
    center_y: float,
    sin_a: float,
    cos_a: float,
    image_width: int,
    image_height: int,
) -> list[list[int]]:
    corners = [(min_x, min_y), (max_x, min_y), (max_x, max_y), (min_x, max_y)]
    points: list[list[int]] = []
    for projected_x, projected_y in corners:
        x = center_x + cos_a * projected_x - sin_a * projected_y
        y = center_y + sin_a * projected_x + cos_a * projected_y
        points.append([
            max(0, min(image_width, int(round(x)))),
            max(0, min(image_height, int(round(y)))),
        ])
    return points

def _is_line_like_horizontal_quad_set(lines: list[list[int]]) -> bool:
    for line in lines:
        if not _is_polygon_line(line):
            return False
        points = np.asarray(line, dtype=float)
        edge_width = max(1.0, float(np.linalg.norm(points[1] - points[0])))
        edge_height = max(1.0, float(np.linalg.norm(points[3] - points[0])))
        if edge_width / edge_height < 3.2:
            return False
    return True

def _has_reasonable_reduced_skew_thickness(base_lines: list[list[int]], candidate_lines: list[list[int]]) -> bool:
    base_heights = np.array([
        max(1, _line_axis_box(line)[3] - _line_axis_box(line)[1] + 1)
        for line in base_lines
    ], dtype=float)
    if base_heights.size == 0:
        return False

    median_base_height = float(np.median(base_heights))
    candidate_heights: list[float] = []
    for line in candidate_lines:
        if not _is_polygon_line(line):
            return False
        points = np.asarray(line, dtype=float)
        candidate_heights.append(max(1.0, float(np.linalg.norm(points[3] - points[0]))))

    return bool(candidate_heights) and max(candidate_heights) <= median_base_height * 2.6
