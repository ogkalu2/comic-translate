from __future__ import annotations
import math
import numpy as np

from .geometry import _is_polygon_line, _line_axis_box
from .scoring import _score_line_candidate
from .clustering import _detect_lines_from_mask

def _filter_noise_lines(lines: list[list[int]], direction: str) -> list[list[int]]:
    from .geometry import _line_axis_box, _is_polygon_line
    filtered = []
    for line in lines:
        x1, y1, x2, y2 = _line_axis_box(line)
        w = max(1, x2 - x1 + 1)
        h = max(1, y2 - y1 + 1)

        if _is_polygon_line(line):
            points = np.asarray(line, dtype=float)[:4]
            h_perp = float(np.linalg.norm(points[3] - points[0]))
            w_perp = float(np.linalg.norm(points[1] - points[0]))
        else:
            h_perp = h
            w_perp = w

        if direction == "horizontal":
            if h_perp < 5 and w_perp < 36:
                continue
            if h_perp < 3:
                continue
        else:
            if w_perp < 5 and h_perp < 36:
                continue
            if w_perp < 3:
                continue
        filtered.append(line)
    return filtered

def _detect_horizontal_lines_skew_aware(text_mask: np.ndarray) -> list[list[int]]:
    base_lines = _filter_noise_lines(_detect_lines_from_mask(text_mask, "horizontal"), "horizontal")
    base_lines = _merge_aligned_horizontal_fragments(base_lines)
    if not base_lines:
        base_lines = [[0, 0, text_mask.shape[1], text_mask.shape[0]]]

    best_lines = base_lines
    base_score = _score_line_candidate(best_lines, "horizontal", text_mask)
    best_score = base_score

    # Pre-extract coordinates to avoid redundant np.where and shifting allocations in the loop
    height, width = text_mask.shape[:2]
    ys, xs = np.where(text_mask)
    if xs.size == 0 or ys.size == 0:
        return best_lines

    center_x = (width - 1) / 2.0
    center_y = (height - 1) / 2.0
    xs_shifted = xs - center_x
    ys_shifted = ys - center_y

    # Pass 1: Coarse search on widely separated angles (refined to include minor and extreme skews)
    coarse_angles = [-33, -24, -15, -6, 6, 15, 24, 33]
    best_coarse_angle = 0
    best_coarse_score = -1_000_000.0
    best_coarse_lines = []

    for angle in coarse_angles:
        candidate = _filter_noise_lines(
            _detect_horizontal_lines_at_angle(text_mask, angle, xs, ys, xs_shifted, ys_shifted),
            "horizontal"
        )
        if not candidate:
            continue
        if len(candidate) > max(len(base_lines) + 2, int(math.ceil(len(base_lines) * 1.6))):
            continue
        if not _is_line_like_horizontal_quad_set(candidate):
            continue
        score = _score_line_candidate(candidate, "horizontal", text_mask)
        if score > best_coarse_score:
            best_coarse_score = score
            best_coarse_angle = angle
            best_coarse_lines = candidate

    # If none of the coarse skewed angles significantly improve or match the 0-degree baseline,
    # we assume the text is perfectly horizontal (no skew) and skip the fine search entirely!
    if best_coarse_score < base_score - 0.15 and base_score >= 1.4:
        return best_lines

    # Pass 2: Fine search in the neighborhood of the best coarse angle (or 0 if no angle won)
    fine_angles = []
    if best_coarse_angle != 0:
        fine_angles.extend([best_coarse_angle - 3, best_coarse_angle, best_coarse_angle + 3])
        fine_angles.extend([-3, 3])
    else:
        fine_angles.extend([-3, 3])

    fine_angles = sorted(list(set(fine_angles)))
    fine_angles = [a for a in fine_angles if -36 <= a <= 36 and a != 0]

    for angle in fine_angles:
        candidate = _filter_noise_lines(
            _detect_horizontal_lines_at_angle(text_mask, angle, xs, ys, xs_shifted, ys_shifted),
            "horizontal"
        )
        if not candidate:
            continue

        if len(candidate) > max(len(base_lines) + 2, int(math.ceil(len(base_lines) * 1.6))):
            continue
        if not _is_line_like_horizontal_quad_set(candidate):
            continue
        score = _score_line_candidate(candidate, "horizontal", text_mask)
        if (
            len(base_lines) >= 2
            and len(candidate) < len(base_lines) - 1
            and score < base_score + 0.35
            and not _has_reasonable_reduced_skew_thickness(base_lines, candidate)
        ):
            continue
        if (
            len(base_lines) >= 2
            and len(candidate) < len(base_lines)
            and _looks_like_distinct_horizontal_rows(base_lines)
            and score < base_score + 0.12
        ):
            continue
        angle_bonus = min(0.12, abs(angle) * 0.006)
        line_count_penalty = 0.04 * max(0, len(candidate) - len(base_lines))
        adjusted_score = score + angle_bonus - line_count_penalty
        if score >= base_score - 0.12 and adjusted_score > best_score + 0.02:
            best_score = adjusted_score
            best_lines = candidate
    return best_lines

def _merge_aligned_horizontal_fragments(lines: list[list[int]]) -> list[list[int]]:
    if len(lines) <= 1 or any(_is_polygon_line(line) for line in lines):
        return lines

    boxes = [_line_axis_box(line) for line in lines]
    heights = np.array([max(1, box[3] - box[1] + 1) for box in boxes], dtype=float)
    median_height = float(np.median(heights)) if heights.size else 12.0
    rows: list[list[list[int]]] = []

    for box in sorted(boxes, key=lambda item: ((item[1] + item[3]) / 2.0, item[0])):
        center_y = (box[1] + box[3]) / 2.0
        matched_row: list[list[int]] | None = None
        for row in rows:
            row_box = _union_axis_boxes(row)
            if row_box is None:
                continue
            row_center_y = (row_box[1] + row_box[3]) / 2.0
            vertical_overlap = min(row_box[3], box[3]) - max(row_box[1], box[1]) + 1
            min_height = min(row_box[3] - row_box[1] + 1, box[3] - box[1] + 1)
            if vertical_overlap >= min_height * 0.45 or abs(center_y - row_center_y) <= max(5.0, median_height * 0.45):
                matched_row = row
                break
        if matched_row is None:
            rows.append([box])
        else:
            matched_row.append(box)

    merged_boxes: list[list[int]] = []
    gap_limit = max(14.0, median_height * 1.55)
    for row in rows:
        row = sorted(row, key=lambda item: item[0])
        current = row[0].copy()
        for box in row[1:]:
            gap = box[0] - current[2] - 1
            vertical_overlap = min(current[3], box[3]) - max(current[1], box[1]) + 1
            current_height = current[3] - current[1] + 1
            box_height = box[3] - box[1] + 1
            min_height = min(current_height, box_height)
            height_ratio = max(current_height, box_height) / max(1, min_height)
            if gap <= gap_limit and vertical_overlap >= min_height * 0.35 and height_ratio <= 1.8:
                current = [
                    min(current[0], box[0]),
                    min(current[1], box[1]),
                    max(current[2], box[2]),
                    max(current[3], box[3]),
                ]
            else:
                merged_boxes.append(current)
                current = box.copy()
        merged_boxes.append(current)

    if len(merged_boxes) >= len(lines):
        return lines
    return sorted(merged_boxes, key=lambda item: (item[1], item[0]))

def _union_axis_boxes(boxes: list[list[int]]) -> list[int] | None:
    if not boxes:
        return None
    return [
        min(box[0] for box in boxes),
        min(box[1] for box in boxes),
        max(box[2] for box in boxes),
        max(box[3] for box in boxes),
    ]

def _detect_horizontal_lines_at_angle(
    text_mask: np.ndarray,
    angle_degrees: float,
    xs: np.ndarray | None = None,
    ys: np.ndarray | None = None,
    xs_shifted: np.ndarray | None = None,
    ys_shifted: np.ndarray | None = None,
) -> list[list[int]]:
    height, width = text_mask.shape[:2]
    if xs is None or ys is None:
        ys, xs = np.where(text_mask)
    if xs.size == 0 or ys.size == 0:
        return [[0, 0, width, height]]

    center_x = (width - 1) / 2.0
    center_y = (height - 1) / 2.0

    if xs_shifted is None or ys_shifted is None:
        xs_shifted = xs - center_x
        ys_shifted = ys - center_y

    angle = math.radians(angle_degrees)
    sin_a = math.sin(angle)
    cos_a = math.cos(angle)
    projected_y = -sin_a * xs_shifted + cos_a * ys_shifted

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

    # Compute median character/glyph height in the block to filter out fake/sliced-off lines
    from .mask import _compute_mask_stats
    mask_stats = _compute_mask_stats(text_mask)
    median_h = mask_stats.median_h
    min_split_h = max(5, int(round(median_h * 0.45)))

    boxes: list[list[int]] = []
    for span_start, span_end in spans:
        selected = (bins >= span_start) & (bins < span_end)
        if not bool(selected.any()):
            continue
        line_xs_shifted = xs_shifted[selected]
        line_ys_shifted = ys_shifted[selected]
        line_projected_x = cos_a * line_xs_shifted + sin_a * line_ys_shifted
        line_projected_y = projected_y[selected]
        min_x = float(line_projected_x.min())
        max_x = float(line_projected_x.max())
        min_y = float(line_projected_y.min())
        max_y = float(line_projected_y.max())
        if (max_x - min_x) < 4 and (max_y - min_y) < 4:
            continue
            
        # Reject rotated lines that are too thin to be real text rows in projection space
        if (max_y - min_y + 1) < min_split_h:
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

def _looks_like_distinct_horizontal_rows(lines: list[list[int]]) -> bool:
    boxes = [_line_axis_box(line) for line in lines]
    if len(boxes) < 2:
        return False

    heights = np.array([max(1, box[3] - box[1] + 1) for box in boxes], dtype=float)
    centers_y = np.array(sorted((box[1] + box[3]) / 2.0 for box in boxes), dtype=float)
    if centers_y.size < 2:
        return False

    median_height = float(np.median(heights))
    median_gap = float(np.median(np.diff(centers_y)))
    return median_gap >= max(8.0, median_height * 1.20)
