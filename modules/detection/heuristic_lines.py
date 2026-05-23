from __future__ import annotations

import math

import imkit as imk
import numpy as np

from modules.utils.textblock import TextBlock


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


def _prepare_text_mask(image: np.ndarray) -> np.ndarray | None:
    text_mask = _text_mask(image)
    if text_mask is None:
        return None
    return _remove_non_text_components(_remove_edge_components(text_mask))


def _text_mask(image: np.ndarray) -> np.ndarray | None:
    if image is None or image.size == 0:
        return None
    gray = imk.to_gray(image)
    threshold, _ = imk.otsu_threshold(gray)
    histogram = np.bincount(gray.reshape(-1), minlength=256)
    fg_pixels = int(histogram[: int(threshold)].sum())
    bg_is_light = fg_pixels < (gray.size * 0.5)
    return gray <= threshold if bg_is_light else gray >= threshold


def _remove_edge_components(text_mask: np.ndarray) -> np.ndarray:
    num_labels, labels, stats, _ = imk.connected_components_with_stats(
        text_mask.astype(np.uint8),
        connectivity=8,
    )
    if num_labels <= 1:
        return text_mask

    height, width = text_mask.shape[:2]
    cleaned = text_mask.copy()
    original_pixels = int(text_mask.sum())

    # 1. Compute median width and height of valid components (ignoring very small noise/dots)
    valid_widths = []
    valid_heights = []
    for label in range(1, num_labels):
        _, _, comp_width, comp_height, area = [int(v) for v in stats[label]]
        if area >= 8:
            valid_widths.append(comp_width)
            valid_heights.append(comp_height)

    if valid_widths:
        median_w = float(np.median(valid_widths))
        median_h = float(np.median(valid_heights))
    else:
        median_w = 12.0
        median_h = 12.0

    # 2. Decide which components to remove
    for label in range(1, num_labels):
        x1, y1, comp_width, comp_height, area = [int(v) for v in stats[label]]
        x2 = x1 + comp_width - 1
        y2 = y1 + comp_height - 1

        # Check if it touches any edge
        touches_left = (x1 <= 1)
        touches_right = (x2 >= width - 2)
        touches_top = (y1 <= 1)
        touches_bottom = (y2 >= height - 2)

        touches_edge = touches_left or touches_right or touches_top or touches_bottom
        if not touches_edge:
            continue

        # If it touches left or right edge, it is almost certainly a bubble/panel border.
        # We always remove it.
        if touches_left or touches_right:
            cleaned[labels == label] = False
            continue

        # Determine if it is a legitimate text character (and should be KEPT)
        # It must have a minimum size to not be considered tiny edge noise/fragments:
        min_char_height = max(4, int(round(median_h * 0.5)))
        is_too_small_noise = (area < 8 or comp_height < min_char_height)

        is_small_crop_relative = (comp_width < width * 0.35 and comp_height < height * 0.35)
        # Allow slightly taller relative height for very small height crops (like 1-2 lines)
        if height < 30 and comp_width < width * 0.35 and comp_height < height * 0.45:
            is_small_crop_relative = True

        is_small_median_relative = (
            comp_width <= max(3.5 * median_w, 24.0) and
            comp_height <= max(3.5 * median_h, 24.0)
        )

        is_character = (is_small_crop_relative or is_small_median_relative) and not is_too_small_noise

        if not is_character:
            cleaned[labels == label] = False

    if int(cleaned.sum()) < max(8, original_pixels * 0.25):
        return text_mask
    return cleaned


def _remove_non_text_components(text_mask: np.ndarray) -> np.ndarray:
    num_labels, labels, stats, _ = imk.connected_components_with_stats(
        text_mask.astype(np.uint8),
        connectivity=8,
    )
    if num_labels <= 1:
        return text_mask

    height, width = text_mask.shape[:2]
    cleaned = text_mask.copy()
    original_pixels = int(text_mask.sum())
    for label in range(1, num_labels):
        x1, y1, comp_width, comp_height, area = [int(v) for v in stats[label]]
        component_density = area / max(1, comp_width * comp_height)
        if comp_width >= width * 0.55 and comp_height >= height * 0.35 and component_density < 0.08:
            cleaned[labels == label] = False

    if int(cleaned.sum()) < max(8, original_pixels * 0.20):
        return text_mask
    return cleaned


def _detect_lines_from_mask(text_mask: np.ndarray, direction: str) -> list[list[int]]:
    height, width = text_mask.shape[:2]
    x_sum = text_mask.sum(axis=0)
    y_sum = text_mask.sum(axis=1)

    tolerance_x = max(1, int(height * 0.02))
    tolerance_y = max(1, int(width * 0.02))

    spans: list[tuple[int, int, int, int]] = []
    if direction == "horizontal":
        start_y = -1
        for y in range(height):
            if int(y_sum[y]) > tolerance_y:
                if start_y == -1:
                    start_y = y
            elif start_y != -1:
                spans.append((0, start_y, width, y))
                start_y = -1
        if start_y != -1:
            spans.append((0, start_y, width, height))
    else:
        start_x = -1
        for x in range(width):
            if int(x_sum[x]) > tolerance_x:
                if start_x == -1:
                    start_x = x
            elif start_x != -1:
                spans.append((start_x, 0, x, height))
                start_x = -1
        if start_x != -1:
            spans.append((start_x, 0, width, height))

    boxes: list[list[int]] = []
    for sx1, sy1, sx2, sy2 in spans:
        region = text_mask[sy1:sy2, sx1:sx2]
        ys, xs = np.where(region)
        if xs.size == 0 or ys.size == 0:
            continue

        if direction == "horizontal":
            boxes.extend(_split_horizontal_span(text_mask, sx1, sy1, sx2, sy2))
        else:
            min_x = sx1 + int(xs.min())
            max_x = sx1 + int(xs.max())
            min_y = sy1 + int(ys.min())
            max_y = sy1 + int(ys.max())
            if (max_x - min_x) < 4 and (max_y - min_y) < 4:
                continue
            boxes.append([min_x, min_y, max_x, max_y])

    if not boxes:
        return [[0, 0, width, height]]
    return boxes


def _split_horizontal_span(text_mask: np.ndarray, sx1: int, sy1: int, sx2: int, sy2: int) -> list[list[int]]:
    region = text_mask[sy1:sy2, sx1:sx2]
    ys, xs = np.where(region)
    if xs.size == 0 or ys.size == 0:
        return []

    component_rows = _split_tall_horizontal_span(region, sx1, sy1)
    if component_rows is not None:
        return component_rows

    min_y = sy1 + int(ys.min())
    max_y = sy1 + int(ys.max())
    line_height = max(1, max_y - min_y + 1)
    gap_limit = max(10, int(line_height * 1.6))

    x_has_ink = region.any(axis=0)
    boxes: list[list[int]] = []
    start_x: int | None = None
    last_ink_x: int | None = None
    gap = 0
    for local_x, has_ink in enumerate(x_has_ink):
        if has_ink:
            if start_x is None:
                start_x = local_x
            last_ink_x = local_x
            gap = 0
            continue

        if start_x is not None:
            gap += 1
            if gap > gap_limit and last_ink_x is not None:
                box = _refine_subspan_box(region, sx1, sy1, start_x, last_ink_x + 1)
                if box is not None:
                    boxes.append(box)
                start_x = None
                last_ink_x = None
                gap = 0

    if start_x is not None and last_ink_x is not None:
        box = _refine_subspan_box(region, sx1, sy1, start_x, last_ink_x + 1)
        if box is not None:
            boxes.append(box)

    return boxes


def _split_tall_horizontal_span(region: np.ndarray, offset_x: int, offset_y: int) -> list[list[int]] | None:
    components = _component_boxes(region)
    if len(components) < 4:
        return None

    median_height = float(np.median([component["height"] for component in components]))
    ys, _ = np.where(region)
    ink_height = int(ys.max() - ys.min() + 1)
    if ink_height < max(36, int(round(median_height * 1.75))):
        return None
    centers_x = np.array([component["cx"] for component in components], dtype=float)
    centers_y = np.array([component["cy"] for component in components], dtype=float)
    if centers_x.size >= 4 and float(centers_x.std()) > 1.0 and float(centers_y.std()) > 1.0:
        correlation = float(np.corrcoef(centers_x, centers_y)[0, 1])
        if abs(correlation) > 0.88:
            return None

    rows = _cluster_components_by_y(components, median_height)
    if len(rows) <= 1:
        return None
    if sum(1 for row in rows if len(row) >= 3) < 2:
        return None

    local_boxes: list[list[int]] = []
    for row in rows:
        for group in _split_component_row_by_x(row, region.shape[1], median_height):
            box = _components_to_box(group)
            if box is not None:
                local_boxes.append(box)

    local_boxes = _merge_left_marginal_boxes(local_boxes, region.shape[1], median_height)
    if len(local_boxes) <= 1:
        return None

    return [[box[0] + offset_x, box[1] + offset_y, box[2] + offset_x, box[3] + offset_y] for box in local_boxes]


def _component_boxes(region: np.ndarray) -> list[dict[str, float]]:
    num_labels, _, stats, centroids = imk.connected_components_with_stats(
        region.astype(np.uint8),
        connectivity=8,
    )
    components: list[dict[str, float]] = []
    for label in range(1, num_labels):
        x1, y1, comp_width, comp_height, area = [int(v) for v in stats[label]]
        if area < 20:
            continue
        components.append({
            "x1": float(x1),
            "y1": float(y1),
            "x2": float(x1 + comp_width - 1),
            "y2": float(y1 + comp_height - 1),
            "width": float(comp_width),
            "height": float(comp_height),
            "area": float(area),
            "cx": float(centroids[label][0]),
            "cy": float(centroids[label][1]),
        })
    return components


def _cluster_components_by_y(components: list[dict[str, float]], median_height: float) -> list[list[dict[str, float]]]:
    rows: list[list[dict[str, float]]] = []
    row_gap = max(8.0, median_height * 0.75)
    for component in sorted(components, key=lambda item: item["cy"]):
        if not rows:
            rows.append([component])
            continue

        row_center = float(np.mean([item["cy"] for item in rows[-1]]))
        if component["cy"] - row_center > row_gap:
            rows.append([component])
        else:
            rows[-1].append(component)
    return rows


def _split_component_row_by_x(
    row: list[dict[str, float]],
    span_width: int,
    median_height: float,
) -> list[list[dict[str, float]]]:
    row = sorted(row, key=lambda item: item["x1"])
    if len(row) <= 1:
        return [row]

    current_max_x = row[0]["x2"]
    for index in range(1, len(row)):
        gap = row[index]["x1"] - current_max_x - 1
        left = row[:index]
        right = row[index:]
        if _is_marginal_component_split(left, right, gap, span_width, median_height):
            return [left, *_split_component_row_by_x(right, span_width, median_height)]
        current_max_x = max(current_max_x, row[index]["x2"])

    groups: list[list[dict[str, float]]] = [[row[0]]]
    current_max_x = row[0]["x2"]
    gap_limit = max(12.0, median_height * 0.85)
    for component in row[1:]:
        gap = component["x1"] - current_max_x - 1
        if gap > gap_limit:
            groups.append([component])
        else:
            groups[-1].append(component)
        current_max_x = max(current_max_x, component["x2"])
    return groups


def _is_marginal_component_split(
    left: list[dict[str, float]],
    right: list[dict[str, float]],
    gap: float,
    span_width: int,
    median_height: float,
) -> bool:
    if gap < max(4.0, median_height * 0.2) or len(right) < 3:
        return False

    left_box = _components_to_box(left)
    right_box = _components_to_box(right)
    if left_box is None or right_box is None:
        return False

    left_width = max(1, left_box[2] - left_box[0] + 1)
    right_width = max(1, right_box[2] - right_box[0] + 1)
    left_height = max(1, left_box[3] - left_box[1] + 1)
    left_center_y = (left_box[1] + left_box[3]) / 2.0
    right_center_y = (right_box[1] + right_box[3]) / 2.0

    near_left_edge = left_box[0] <= span_width * 0.28 and left_box[2] <= span_width * 0.42
    right_is_main_text = right_width >= max(left_width * 1.35, median_height * 4.0)
    left_is_side_note = left_height >= median_height * 1.25 or abs(left_center_y - right_center_y) >= median_height * 0.35
    return near_left_edge and right_is_main_text and left_is_side_note


def _components_to_box(components: list[dict[str, float]]) -> list[int] | None:
    if not components:
        return None
    return [
        int(math.floor(min(component["x1"] for component in components))),
        int(math.floor(min(component["y1"] for component in components))),
        int(math.ceil(max(component["x2"] for component in components))),
        int(math.ceil(max(component["y2"] for component in components))),
    ]


def _merge_left_marginal_boxes(boxes: list[list[int]], span_width: int, median_height: float) -> list[list[int]]:
    if len(boxes) <= 2:
        return boxes

    left_boxes = [
        box for box in boxes
        if box[0] <= span_width * 0.28 and box[2] <= span_width * 0.42 and (box[2] - box[0] + 1) <= span_width * 0.32
    ]
    if len(left_boxes) < 2:
        return boxes

    left_boxes = sorted(left_boxes, key=lambda box: (box[1], box[0]))
    merged_left: list[list[int]] = []
    consumed: set[int] = set()
    for index, box in enumerate(left_boxes):
        if index in consumed:
            continue
        merged = box.copy()
        consumed.add(index)
        for other_index in range(index + 1, len(left_boxes)):
            other = left_boxes[other_index]
            vertical_gap = max(0, max(merged[1], other[1]) - min(merged[3], other[3]))
            horizontal_gap = max(0, max(merged[0], other[0]) - min(merged[2], other[2]))
            union = [
                min(merged[0], other[0]),
                min(merged[1], other[1]),
                max(merged[2], other[2]),
                max(merged[3], other[3]),
            ]
            if vertical_gap <= median_height * 0.8 and horizontal_gap <= median_height * 1.2 and (union[3] - union[1] + 1) <= median_height * 4.8:
                merged = union
                consumed.add(other_index)
        merged_left.append(merged)

    left_set = {tuple(box) for box in left_boxes}
    remaining = [box for box in boxes if tuple(box) not in left_set]
    return remaining + merged_left


def _refine_subspan_box(
    region: np.ndarray,
    offset_x: int,
    offset_y: int,
    local_x1: int,
    local_x2: int,
) -> list[int] | None:
    subregion = region[:, local_x1:local_x2]
    ys, xs = np.where(subregion)
    if xs.size == 0 or ys.size == 0:
        return None

    min_x = offset_x + local_x1 + int(xs.min())
    max_x = offset_x + local_x1 + int(xs.max())
    min_y = offset_y + int(ys.min())
    max_y = offset_y + int(ys.max())
    if (max_x - min_x) < 4 and (max_y - min_y) < 4:
        return None
    return [min_x, min_y, max_x, max_y]


def _detect_horizontal_lines_skew_aware(text_mask: np.ndarray) -> list[list[int]]:
    base_lines = _detect_lines_from_mask(text_mask, "horizontal")
    best_lines = base_lines
    base_score = _score_line_candidate(base_lines, "horizontal", text_mask)
    best_score = base_score

    # Small signs and handwritten notes are often mildly skewed. Try a coarse
    # de-skewed projection. If the candidate explains the same text nearly as
    # well and keeps the same line count, prefer its quadrilateral geometry.
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


def _score_line_candidate(lines: list[list[int]], direction: str, text_mask: np.ndarray) -> float:
    if not lines:
        return -1_000_000.0

    total_text_pixels = int(text_mask.sum())
    if total_text_pixels <= 0:
        return -1_000_000.0

    covered_pixels = 0
    total_area = 0.0
    shape_scores: list[float] = []
    for line in lines:
        line_pixels, line_area, line_width, line_height = _line_coverage_metrics(line, text_mask)
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

    # Wrong-axis projection often turns a text line into many character-sized
    # fragments. Penalize that over-segmentation without forbidding multi-line text.
    fragmentation_penalty = 0.08 * max(0, len(lines) - 1)

    return coverage * 1.4 + density * 0.8 + shape_score * 1.2 - fragmentation_penalty


def _line_coverage_metrics(line, text_mask: np.ndarray) -> tuple[int, float, float, float]:
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

        ink_points = np.column_stack((xs + x1, ys + y1)).astype(float)
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
    return int(text_mask[y1:y2 + 1, x1:x2 + 1].sum()), line_width * line_height, line_width, line_height


def _is_large_glyph_horizontal(
    text_mask: np.ndarray,
    horizontal_lines: list[list[int]],
    vertical_lines: list[list[int]],
) -> bool:
    union = _union_box(horizontal_lines + vertical_lines)
    if union is None:
        return False

    width = max(1, union[2] - union[0] + 1)
    height = max(1, union[3] - union[1] + 1)
    if width < height * 0.9 or len(horizontal_lines) > 2 or len(vertical_lines) > 4:
        return False

    num_labels, _, stats, centroids = imk.connected_components_with_stats(
        text_mask.astype(np.uint8),
        connectivity=8,
    )
    components = []
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

    union = _union_box(horizontal_lines)
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


def _is_sparse_horizontal_overfit(
    text_mask: np.ndarray,
    horizontal_lines: list[list[int]],
    vertical_lines: list[list[int]],
    horizontal_score: float,
    vertical_score: float,
) -> bool:
    if len(horizontal_lines) < 5 or len(vertical_lines) < len(horizontal_lines):
        return False

    mask_density = int(text_mask.sum()) / max(1, text_mask.shape[0] * text_mask.shape[1])
    if mask_density >= 0.06 or vertical_score < horizontal_score - 0.12:
        return False

    densities: list[float] = []
    for line in horizontal_lines:
        pixels, area, _, _ = _line_coverage_metrics(line, text_mask)
        if area > 0:
            densities.append(pixels / area)

    return bool(densities) and float(np.median(densities)) < 0.09


def _detect_sparse_vertical_component_columns(text_mask: np.ndarray) -> list[list[int]]:
    components = _component_boxes(text_mask)
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


def _pad_line_boxes(lines: list[list[int]], direction: str, width: int, height: int) -> list[list[int]]:
    padded: list[list[int]] = []
    for line in lines:
        if _is_polygon_line(line):
            padded.append(_pad_polygon_line(line, direction, width, height))
            continue

        x1, y1, x2, y2 = [int(v) for v in line]
        line_width = max(1, x2 - x1 + 1)
        line_height = max(1, y2 - y1 + 1)
        if direction == "horizontal":
            dx = max(1, int(round(line_height * 0.10)))
            dy = max(1, int(round(line_height * 0.12)))
        else:
            dx = max(1, int(round(line_width * 0.12)))
            dy = max(1, int(round(line_width * 0.10)))
        padded.append(_clamp_box([x1 - dx, y1 - dy, x2 + dx, y2 + dy], width, height))
    return padded


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


def _is_polygon_line(line) -> bool:
    arr = np.asarray(line)
    return arr.ndim == 2 and arr.shape[0] >= 4 and arr.shape[1] == 2


def _line_axis_box(line) -> list[int]:
    if _is_polygon_line(line):
        arr = np.asarray(line, dtype=float)
        return [
            int(math.floor(float(arr[:, 0].min()))),
            int(math.floor(float(arr[:, 1].min()))),
            int(math.ceil(float(arr[:, 0].max()))),
            int(math.ceil(float(arr[:, 1].max()))),
        ]
    return [int(round(float(v))) for v in np.asarray(line).reshape(-1)[:4]]


def _offset_line(line, offset_x: int, offset_y: int):
    if _is_polygon_line(line):
        return [[int(point[0]) + offset_x, int(point[1]) + offset_y] for point in line]
    return [int(line[0]) + offset_x, int(line[1]) + offset_y, int(line[2]) + offset_x, int(line[3]) + offset_y]


def _pad_polygon_line(line, direction: str, width: int, height: int) -> list[list[int]]:
    points = np.asarray(line, dtype=float)
    center = points.mean(axis=0)
    edge_width = max(1.0, float(np.linalg.norm(points[1] - points[0])))
    edge_height = max(1.0, float(np.linalg.norm(points[3] - points[0])))
    local_x = (points[1] - points[0]) / edge_width
    local_y = (points[3] - points[0]) / edge_height

    if direction == "horizontal":
        x_scale = (edge_width + max(2.0, edge_height * 0.20)) / edge_width
        y_scale = (edge_height + max(2.0, edge_height * 0.24)) / edge_height
    else:
        x_scale = (edge_width + max(2.0, edge_width * 0.24)) / edge_width
        y_scale = (edge_height + max(2.0, edge_width * 0.20)) / edge_height

    padded: list[list[int]] = []
    for point in points:
        delta = point - center
        expanded = center + local_x * np.dot(delta, local_x) * x_scale + local_y * np.dot(delta, local_y) * y_scale
        padded.append([
            max(0, min(width, int(round(float(expanded[0]))))),
            max(0, min(height, int(round(float(expanded[1]))))),
        ])
    return padded


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


def _infer_direction(lines: list[list[int]], block_box: list[int], source_language: str) -> str:
    if lines:
        horizontal = 0.0
        vertical = 0.0
        for line in lines:
            x1, y1, x2, y2 = _line_axis_box(line)
            width = max(1, x2 - x1)
            height = max(1, y2 - y1)
            horizontal += max(0.0, width / height - 1.0)
            vertical += max(0.0, height / width - 1.0)
        if vertical > horizontal * 1.15 + 0.2:
            return "vertical"
        if horizontal > vertical * 1.15 + 0.2:
            return "horizontal"

    union = _union_box(lines) if lines else block_box
    return _fallback_direction(union, source_language)


def _sort_lines(lines: list[list[int]], direction: str) -> list[list[int]]:
    if direction == "vertical":
        return sorted((_normalize_line(line) for line in lines), key=lambda line: (-_line_axis_box(line)[0], _line_axis_box(line)[1]))
    return sorted((_normalize_line(line) for line in lines), key=lambda line: (_line_axis_box(line)[1], _line_axis_box(line)[0]))


def _normalize_line(line):
    if _is_polygon_line(line):
        return [[int(round(float(point[0]))), int(round(float(point[1])))] for point in line]
    return [int(round(float(v))) for v in np.asarray(line).reshape(-1)[:4]]


def _projection_hint(block: list[int], source_language: str) -> str | None:
    normalized = _normalize_source_language(source_language)
    if normalized == "ko":
        return "horizontal"
    if normalized not in {"ja", "zh"}:
        return "horizontal"

    width = max(1, block[2] - block[0])
    height = max(1, block[3] - block[1])
    if width > height * 1.25:
        return "horizontal"
    if height > width * 1.25:
        return "vertical"
    return None


def _fallback_direction(box: list[int], source_language: str) -> str:
    width = max(1, box[2] - box[0])
    height = max(1, box[3] - box[1])
    aspect_direction = "vertical" if height > width * 1.15 else "horizontal"

    normalized = _normalize_source_language(source_language)
    if normalized == "ko":
        return "horizontal"
    if normalized in {"ja", "zh"} and 0.85 <= height / width <= 1.15:
        return "vertical" if height >= width * 0.9 else "horizontal"
    return aspect_direction


def _normalize_source_language(source_language: str) -> str:
    value = (source_language or "").strip().lower()
    if value in {"ja", "japanese"}:
        return "ja"
    if value in {"ko", "korean"}:
        return "ko"
    if value in {"zh", "ch"} or value.startswith("zh-") or "chinese" in value:
        return "zh"
    return "other"


def _to_box(box) -> list[int]:
    return [int(round(float(v))) for v in box]


def _clamp_box(box: list[int], width: int, height: int) -> list[int]:
    x1 = max(0, min(width, int(round(box[0]))))
    y1 = max(0, min(height, int(round(box[1]))))
    x2 = max(0, min(width, int(round(box[2]))))
    y2 = max(0, min(height, int(round(box[3]))))
    return [min(x1, x2), min(y1, y2), max(x1, x2), max(y1, y2)]


def _expand_box(box: list[int], width_percent: float, height_percent: float, image_width: int, image_height: int) -> list[int]:
    width = box[2] - box[0]
    height = box[3] - box[1]
    dx = width * width_percent / 100.0
    dy = height * height_percent / 100.0
    return _clamp_box([box[0] - dx, box[1] - dy, box[2] + dx, box[3] + dy], image_width, image_height)


def _union_box(lines: list[list[int]]) -> list[int] | None:
    if not lines:
        return None
    boxes = [_line_axis_box(line) for line in lines]
    xs1 = [box[0] for box in boxes]
    ys1 = [box[1] for box in boxes]
    xs2 = [box[2] for box in boxes]
    ys2 = [box[3] for box in boxes]
    return [min(xs1), min(ys1), max(xs2), max(ys2)]
