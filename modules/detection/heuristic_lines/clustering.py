from __future__ import annotations
import math
import numpy as np
import imkit as imk

from .mask import _mask_bounds, _sum_box_pixels

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
        bounds = _mask_bounds(region)
        if bounds is None:
            continue

        if direction == "horizontal":
            boxes.extend(_split_horizontal_span(text_mask, sx1, sy1, sx2, sy2))
        else:
            min_x = sx1 + bounds[0]
            max_x = sx1 + bounds[2]
            min_y = sy1 + bounds[1]
            max_y = sy1 + bounds[3]
            if (max_x - min_x) < 4 and (max_y - min_y) < 4:
                continue
            boxes.append([min_x, min_y, max_x, max_y])

    if not boxes:
        return [[0, 0, width, height]]
    return boxes

def _find_horizontal_valley_splits(region: np.ndarray) -> list[int]:
    h, w = region.shape[:2]
    if h < 36:
        return _find_compact_horizontal_valley_splits(region)

    y_sum = region.sum(axis=1)
    max_peak = int(y_sum.max())
    if max_peak <= 0:
        return []

    valley_thresh = min(0.12 * max_peak, 0.08 * w)
    valley_thresh = max(4.0, valley_thresh)

    valley_runs = []
    current_run = []
    for y in range(h):
        if float(y_sum[y]) <= valley_thresh:
            current_run.append(y)
        else:
            if current_run:
                valley_runs.append(current_run)
                current_run = []
    if current_run:
        valley_runs.append(current_run)

    splits = []
    for run in valley_runs:
        if run[0] <= 3 or run[-1] >= h - 4:
            continue

        # Require at least 2 consecutive near-zero rows in the gap by default.
        # Dense handwritten captions can have real row gaps with a few ink
        # pixels from descenders/overlapping strokes, so allow those only when
        # the valley is a strong local minimum with text peaks on both sides.
        near_zero_streak = 0
        for y in run:
            if float(y_sum[y]) <= 1:
                near_zero_streak += 1
                if near_zero_streak >= 2:
                    break
            else:
                near_zero_streak = 0
        if near_zero_streak < 2 and not _is_soft_horizontal_valley(y_sum, run, max_peak, w):
            continue

        min_y = run[0]
        min_val = float(y_sum[min_y])
        for y in run:
            val = float(y_sum[y])
            if val < min_val:
                min_val = val
                min_y = y
        splits.append(min_y)

    return splits

def _find_compact_horizontal_valley_splits(region: np.ndarray) -> list[int]:
    h, w = region.shape[:2]
    if h < 10:
        return []

    y_sum = region.sum(axis=1)
    max_peak = int(y_sum.max())
    if max_peak < max(12, int(round(w * 0.18))):
        return []

    valley_thresh = max(1.0, min(3.0, 0.10 * max_peak))
    valley_runs: list[list[int]] = []
    current_run: list[int] = []
    for y in range(h):
        if float(y_sum[y]) <= valley_thresh:
            current_run.append(y)
        else:
            if current_run:
                valley_runs.append(current_run)
                current_run = []
    if current_run:
        valley_runs.append(current_run)

    splits: list[int] = []
    for run in valley_runs:
        if len(run) < 2 or run[0] <= 1 or run[-1] >= h - 2:
            continue

        left_peak = float(y_sum[: run[0]].max()) if run[0] > 0 else 0.0
        right_peak = float(y_sum[run[-1] + 1 :].max()) if run[-1] + 1 < y_sum.size else 0.0
        if min(left_peak, right_peak) < max(10.0, 0.35 * max_peak):
            continue

        min_y = run[0]
        min_val = float(y_sum[min_y])
        for y in run:
            val = float(y_sum[y])
            if val < min_val:
                min_val = val
                min_y = y
        splits.append(min_y)

    return splits

def _is_soft_horizontal_valley(y_sum: np.ndarray, run: list[int], max_peak: int, width: int) -> bool:
    if len(run) < 3 or max_peak <= 0:
        return False

    run_values = np.asarray([float(y_sum[y]) for y in run], dtype=float)
    min_val = float(run_values.min())
    soft_thresh = max(8.0, min(0.06 * max_peak, 0.04 * width))
    if min_val > soft_thresh:
        return False

    left_peak = float(y_sum[: run[0]].max()) if run[0] > 0 else 0.0
    right_peak = float(y_sum[run[-1] + 1 :].max()) if run[-1] + 1 < y_sum.size else 0.0
    side_peak_thresh = max(12.0, 0.18 * max_peak)
    if left_peak < side_peak_thresh or right_peak < side_peak_thresh:
        return False

    return min_val <= min(left_peak, right_peak) * 0.35

def _split_horizontal_span(text_mask: np.ndarray, sx1: int, sy1: int, sx2: int, sy2: int) -> list[list[int]]:
    region = text_mask[sy1:sy2, sx1:sx2]
    bounds = _mask_bounds(region)
    if bounds is None:
        return []

    splits = _find_horizontal_valley_splits(region)
    if splits:
        sub_boxes = []
        last_y = 0
        for split_y in splits:
            sub_boxes.extend(_split_horizontal_span(text_mask, sx1, sy1 + last_y, sx2, sy1 + split_y))
            last_y = split_y + 1
        sub_boxes.extend(_split_horizontal_span(text_mask, sx1, sy1 + last_y, sx2, sy2))
        return sub_boxes

    component_rows = _split_tall_horizontal_span(region, sx1, sy1)
    if component_rows is not None:
        return component_rows

    min_y = sy1 + bounds[1]
    max_y = sy1 + bounds[3]
    line_height = max(1, max_y - min_y + 1)
    gap_limit = max(10, int(line_height * 2.8))

    x_has_ink = region.any(axis=0)
    boxes: list[list[int]] = []
    start_x: int | None = None
    last_ink_x: int | None = None
    gap = 0
    min_width_threshold = max(24, int(region.shape[1] * 0.10))

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
                w = last_ink_x + 1 - start_x
                if w >= min_width_threshold or len(boxes) == 0:
                    box = _refine_subspan_box(region, sx1, sy1, start_x, last_ink_x + 1)
                    if box is not None:
                        boxes.append(box)
                start_x = None
                last_ink_x = None
                gap = 0

    if start_x is not None and last_ink_x is not None:
        w = last_ink_x + 1 - start_x
        if w >= min_width_threshold or len(boxes) == 0:
            box = _refine_subspan_box(region, sx1, sy1, start_x, last_ink_x + 1)
            if box is not None:
                boxes.append(box)

    return boxes

def _trim_marginal_vertical_noise_from_horizontal_lines(
    lines: list[list[int]],
    text_mask: np.ndarray,
    vertical_lines: list[list[int]],
    component_boxes: list[dict[str, float]] | None = None,
    integral_image: np.ndarray | None = None,
) -> list[list[int]]:
    from .geometry import _is_polygon_line, _line_axis_box

    if len(lines) < 2 or len(vertical_lines) < 2:
        return lines
    if any(_is_polygon_line(line) for line in lines):
        return lines

    vertical_boxes = [_line_axis_box(line) for line in vertical_lines]
    if integral_image is None:
        integral_image = text_mask.astype(np.int32, copy=False).cumsum(axis=0).cumsum(axis=1)
    vertical_pixels = []
    for box in vertical_boxes:
        x1 = max(0, box[0])
        y1 = max(0, box[1])
        x2 = min(text_mask.shape[1] - 1, box[2])
        y2 = min(text_mask.shape[0] - 1, box[3])
        if x2 < x1 or y2 < y1:
            vertical_pixels.append(0)
            continue
        vertical_pixels.append(_sum_box_pixels(integral_image, x1, y1, x2, y2))
    if not vertical_pixels:
        return lines

    main_index = int(np.argmax(vertical_pixels))
    main_box = vertical_boxes[main_index]
    main_pixels = max(1, vertical_pixels[main_index])
    main_width = max(1, main_box[2] - main_box[0] + 1)
    main_height = max(1, main_box[3] - main_box[1] + 1)

    components = component_boxes if component_boxes is not None else _component_boxes(text_mask)
    median_height = float(np.median([component["height"] for component in components])) if components else 12.0

    marginal_columns: list[tuple[str, list[int]]] = []
    for index, box in enumerate(vertical_boxes):
        if index == main_index:
            continue
        width = max(1, box[2] - box[0] + 1)
        height = max(1, box[3] - box[1] + 1)
        gap_left = main_box[0] - box[2] - 1
        gap_right = box[0] - main_box[2] - 1
        side = "left" if gap_left >= 0 else "right" if gap_right >= 0 else ""
        if not side:
            continue
        if max(gap_left, gap_right) < max(6.0, median_height * 0.25):
            continue
        if width > max(main_width * 0.65, median_height * 4.0):
            continue
        if height < max(median_height * 2.5, main_height * 0.35):
            continue
        if vertical_pixels[index] > main_pixels * 0.35:
            continue
        starts_later = box[1] > main_box[1] + median_height
        if not starts_later:
            continue
        marginal_columns.append((side, box))

    if not marginal_columns:
        return lines

    trimmed_lines: list[list[int]] = []
    for line in lines:
        x1, y1, x2, y2 = _line_axis_box(line)
        refined = [x1, y1, x2, y2]
        for side, column in marginal_columns:
            line_height = max(1, refined[3] - refined[1] + 1)
            overlap_y = max(0, min(refined[3], column[3]) - max(refined[1], column[1]) + 1)
            if overlap_y < max(2, int(round(line_height * 0.25))):
                continue
            if _has_intervening_text_ink(
                text_mask,
                integral_image,
                refined,
                main_box,
                column,
                side,
            ):
                continue

            if side == "left" and refined[0] <= column[2] and refined[2] >= main_box[0]:
                candidate = _refine_box_in_range(text_mask, main_box[0], refined[1], refined[2], refined[3])
                if candidate is not None:
                    refined = candidate
            elif side == "right" and refined[2] >= column[0] and refined[0] <= main_box[2]:
                candidate = _refine_box_in_range(text_mask, refined[0], refined[1], main_box[2], refined[3])
                if candidate is not None:
                    refined = candidate
        trimmed_lines.append(refined)

    return trimmed_lines

def _has_intervening_text_ink(
    text_mask: np.ndarray,
    integral_image: np.ndarray,
    line_box: list[int],
    main_box: list[int],
    column: list[int],
    side: str,
) -> bool:
    if side == "left":
        x1 = column[2] + 1
        x2 = main_box[0] - 1
    elif side == "right":
        x1 = main_box[2] + 1
        x2 = column[0] - 1
    else:
        return False

    height, width = text_mask.shape[:2]
    y1 = max(0, min(height - 1, int(line_box[1])))
    y2 = max(0, min(height - 1, int(line_box[3])))
    x1 = max(0, min(width - 1, int(x1)))
    x2 = max(0, min(width - 1, int(x2)))
    if x2 < x1 or y2 < y1:
        return False

    line_height = max(1, y2 - y1 + 1)
    bridge_pixels = _sum_box_pixels(integral_image, x1, y1, x2, y2)
    if bridge_pixels < max(12, int(round(line_height * 0.75))):
        return False

    bridge = text_mask[y1 : y2 + 1, x1 : x2 + 1]
    bridge_width = max(1, x2 - x1 + 1)
    ink_columns = int(bridge.any(axis=0).sum())
    return ink_columns >= max(3, min(12, int(round(bridge_width * 0.08))))

def _merge_small_horizontal_fragments(lines: list[list[int]]) -> list[list[int]]:
    from .geometry import _is_polygon_line, _line_axis_box

    if len(lines) <= 1:
        return lines
    if any(_is_polygon_line(line) for line in lines):
        return lines

    boxes = [_line_axis_box(line) for line in lines]
    widths = np.array([max(1, box[2] - box[0] + 1) for box in boxes], dtype=float)
    heights = np.array([max(1, box[3] - box[1] + 1) for box in boxes], dtype=float)
    median_width = float(np.median(widths)) if widths.size else 24.0
    median_height = float(np.median(heights)) if heights.size else 12.0

    consumed: set[int] = set()
    for index, box in enumerate(boxes):
        if index in consumed:
            continue

        box_width = max(1, box[2] - box[0] + 1)
        box_height = max(1, box[3] - box[1] + 1)
        is_small_fragment = (
            box_height <= max(8.0, median_height * 0.45)
            and box_width <= max(36.0, median_width * 0.35)
        )
        if not is_small_fragment:
            continue

        center_x = (box[0] + box[2]) / 2.0
        best_target: int | None = None
        best_gap: float | None = None
        for target_index, target in enumerate(boxes):
            if target_index == index or target_index in consumed:
                continue
            target_width = max(1, target[2] - target[0] + 1)
            target_height = max(1, target[3] - target[1] + 1)
            if target_width < box_width * 2.0 and target_height < box_height * 2.0:
                continue

            # Ensure there is vertical overlap between the fragment and the target line.
            # Fragments belonging to the same horizontal text row should overlap vertically.
            vertical_overlap = min(box[3], target[3]) - max(box[1], target[1]) + 1
            min_h = min(box_height, target_height)
            if min_h <= 0 or (vertical_overlap / min_h) < 0.20:
                continue

            vertical_gap = max(0, max(box[1], target[1]) - min(box[3], target[3]) - 1)
            if vertical_gap > max(8.0, median_height * 0.45):
                continue

            horizontal_overlap = min(box[2], target[2]) - max(box[0], target[0]) + 1
            center_in_target = target[0] - median_height <= center_x <= target[2] + median_height
            enough_overlap = horizontal_overlap >= min(box_width * 0.35, 8.0)
            if not center_in_target and not enough_overlap:
                continue

            if best_gap is None or vertical_gap < best_gap:
                best_gap = float(vertical_gap)
                best_target = target_index

        if best_target is None:
            continue

        target = boxes[best_target]
        boxes[best_target] = [
            min(target[0], box[0]),
            min(target[1], box[1]),
            max(target[2], box[2]),
            max(target[3], box[3]),
        ]
        consumed.add(index)

    if not consumed:
        return lines
    return [box for index, box in enumerate(boxes) if index not in consumed]

def _filter_marginal_horizontal_artifacts(
    lines: list[list[int]],
    text_mask: np.ndarray,
) -> list[list[int]]:
    from .geometry import _is_polygon_line, _line_axis_box

    if len(lines) <= 1:
        return lines
    if any(_is_polygon_line(line) for line in lines):
        return lines

    width = text_mask.shape[1]
    boxes = [_line_axis_box(line) for line in lines]
    line_widths = np.array([max(1, box[2] - box[0] + 1) for box in boxes], dtype=float)
    line_heights = np.array([max(1, box[3] - box[1] + 1) for box in boxes], dtype=float)
    median_width = float(np.median(line_widths)) if line_widths.size else 24.0
    median_height = float(np.median(line_heights)) if line_heights.size else 12.0

    edge_margin = max(4, int(round(width * 0.03)))
    max_artifact_width = max(40.0, median_width * 0.18)
    max_artifact_height = max(12.0, median_height * 0.80)
    kept: list[list[int]] = []
    for index, box in enumerate(boxes):
        line_width = max(1, box[2] - box[0] + 1)
        line_height = max(1, box[3] - box[1] + 1)
        touches_edge = box[0] <= edge_margin or box[2] >= width - 1 - edge_margin
        if not touches_edge or line_width > max_artifact_width or line_height > max_artifact_height:
            kept.append(box)
            continue

        overlaps_other_text = False
        for other_index, other in enumerate(boxes):
            if other_index == index:
                continue
            other_width = max(1, other[2] - other[0] + 1)
            if other_width <= line_width:
                continue
            horizontal_overlap = min(box[2], other[2]) - max(box[0], other[0]) + 1
            horizontal_gap = max(0, max(box[0], other[0]) - min(box[2], other[2]) - 1)
            vertical_overlap = min(box[3], other[3]) - max(box[1], other[1]) + 1
            min_height = min(line_height, max(1, other[3] - other[1] + 1))
            meaningful_overlap = horizontal_overlap >= max(8.0, line_width * 0.35)
            same_row_neighbor = (
                horizontal_overlap <= 0
                and horizontal_gap <= max(8.0, median_height * 0.35)
                and vertical_overlap >= max(2.0, min_height * 0.25)
            )
            if meaningful_overlap or same_row_neighbor:
                overlaps_other_text = True
                break

        if overlaps_other_text:
            kept.append(box)

    return kept or lines

def _refine_box_in_range(text_mask: np.ndarray, x1: int, y1: int, x2: int, y2: int) -> list[int] | None:
    h, w = text_mask.shape[:2]
    x1 = max(0, min(w - 1, int(x1)))
    x2 = max(0, min(w - 1, int(x2)))
    y1 = max(0, min(h - 1, int(y1)))
    y2 = max(0, min(h - 1, int(y2)))
    if x2 < x1 or y2 < y1:
        return None

    region = text_mask[y1 : y2 + 1, x1 : x2 + 1]
    bounds = _mask_bounds(region)
    if bounds is None:
        return None
    bx1, by1, bx2, by2 = bounds
    return [x1 + bx1, y1 + by1, x1 + bx2, y1 + by2]

def _split_tall_horizontal_span(region: np.ndarray, offset_x: int, offset_y: int) -> list[list[int]] | None:
    components = _component_boxes(region)
    if len(components) < 4:
        return None

    median_height = float(np.median([component["height"] for component in components]))
    bounds = _mask_bounds(region)
    if bounds is None:
        return None
    ink_height = bounds[3] - bounds[1] + 1
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

    row_bands = _component_row_bands(rows, region.shape[0])
    local_boxes: list[list[int]] = []
    for row, (band_y1, band_y2) in zip(rows, row_bands):
        for group in _split_component_row_by_x(row, region.shape[1], median_height):
            box = _components_to_band_box(group, region, band_y1, band_y2)
            if box is not None:
                local_boxes.append(box)

    local_boxes = _merge_left_marginal_boxes(local_boxes, region.shape[1], median_height)
    if len(local_boxes) <= 1:
        return None

    return [[box[0] + offset_x, box[1] + offset_y, box[2] + offset_x, box[3] + offset_y] for box in local_boxes]

def _component_row_bands(rows: list[list[dict[str, float]]], region_height: int) -> list[tuple[int, int]]:
    if not rows:
        return []
    if len(rows) == 1:
        return [(0, region_height)]

    centers = [float(np.mean([component["cy"] for component in row])) for row in rows]
    boundaries = [0]
    for index in range(len(rows) - 1):
        boundary = int(round((centers[index] + centers[index + 1]) / 2.0))
        boundary = max(boundaries[-1] + 1, min(region_height - 1, boundary))
        boundaries.append(boundary)
    boundaries.append(region_height)
    return [(boundaries[index], boundaries[index + 1]) for index in range(len(boundaries) - 1)]

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
    row_center_sums: list[float] = []
    row_counts: list[int] = []
    for component in sorted(components, key=lambda item: item["cy"]):
        if not rows:
            rows.append([component])
            row_center_sums.append(component["cy"])
            row_counts.append(1)
            continue

        row_center = row_center_sums[-1] / row_counts[-1]
        if component["cy"] - row_center > row_gap:
            rows.append([component])
            row_center_sums.append(component["cy"])
            row_counts.append(1)
        else:
            rows[-1].append(component)
            row_center_sums[-1] += component["cy"]
            row_counts[-1] += 1
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
    group_boxes: list[list[float]] = [[row[0]["x1"], row[0]["y1"], row[0]["x2"], row[0]["y2"]]]
    gap_limit = max(12.0, median_height * 0.85)
    for component in row[1:]:
        gap = component["x1"] - current_max_x - 1
        previous_box = group_boxes[-1]
        if gap > gap_limit and not _is_trailing_punctuation_component_box(previous_box, component, gap, median_height):
            groups.append([component])
            group_boxes.append([component["x1"], component["y1"], component["x2"], component["y2"]])
        else:
            groups[-1].append(component)
            previous_box[0] = min(previous_box[0], component["x1"])
            previous_box[1] = min(previous_box[1], component["y1"])
            previous_box[2] = max(previous_box[2], component["x2"])
            previous_box[3] = max(previous_box[3], component["y2"])
        current_max_x = max(current_max_x, component["x2"])
    return groups

def _is_trailing_punctuation_component_box(
    previous_box: list[float],
    component: dict[str, float],
    gap: float,
    median_height: float,
) -> bool:
    previous_width = max(1.0, previous_box[2] - previous_box[0] + 1)
    component_width = max(1.0, component["width"])
    component_height = max(1.0, component["height"])
    previous_center_y = (previous_box[1] + previous_box[3]) / 2.0
    component_center_y = (component["y1"] + component["y2"]) / 2.0

    if gap > max(48.0, median_height * 3.0):
        return False
    if component_width > max(8.0, median_height * 0.60):
        return False
    if component_height > max(14.0, median_height * 0.95):
        return False
    if previous_width < max(36.0, median_height * 3.0):
        return False
    return abs(previous_center_y - component_center_y) <= max(10.0, median_height * 0.90)

def _is_trailing_punctuation_component(
    previous_group: list[dict[str, float]],
    component: dict[str, float],
    gap: float,
    median_height: float,
) -> bool:
    previous_box = _components_to_box(previous_group)
    if previous_box is None:
        return False

    previous_width = max(1, previous_box[2] - previous_box[0] + 1)
    component_width = max(1.0, component["width"])
    component_height = max(1.0, component["height"])
    previous_center_y = (previous_box[1] + previous_box[3]) / 2.0
    component_center_y = (component["y1"] + component["y2"]) / 2.0

    if gap > max(48.0, median_height * 3.0):
        return False
    if component_width > max(8.0, median_height * 0.60):
        return False
    if component_height > max(14.0, median_height * 0.95):
        return False
    if previous_width < max(36.0, median_height * 3.0):
        return False
    return abs(previous_center_y - component_center_y) <= max(10.0, median_height * 0.90)

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

def _components_to_band_box(
    components: list[dict[str, float]],
    region: np.ndarray,
    band_y1: int,
    band_y2: int,
) -> list[int] | None:
    box = _components_to_box(components)
    if box is None:
        return None

    x1 = max(0, min(region.shape[1] - 1, box[0]))
    x2 = max(0, min(region.shape[1] - 1, box[2]))
    y1 = max(0, min(region.shape[0], band_y1))
    y2 = max(0, min(region.shape[0], band_y2))
    if x2 < x1 or y2 <= y1:
        return box

    subregion = region[y1:y2, x1 : x2 + 1]
    bounds = _mask_bounds(subregion)
    if bounds is None:
        return box
    bx1, by1, bx2, by2 = bounds
    return [x1 + bx1, y1 + by1, x1 + bx2, y1 + by2]

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
    bounds = _mask_bounds(subregion)
    if bounds is None:
        return None

    min_x = offset_x + local_x1 + bounds[0]
    max_x = offset_x + local_x1 + bounds[2]
    min_y = offset_y + bounds[1]
    max_y = offset_y + bounds[3]
    if (max_x - min_x) < 4 and (max_y - min_y) < 4:
        return None
    return [min_x, min_y, max_x, max_y]
