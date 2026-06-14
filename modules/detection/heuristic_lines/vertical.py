from __future__ import annotations
import math
import numpy as np

from .geometry import _line_axis_box, _union_box, _pad_line_boxes
from .mask import _mask_bounds
from .scoring import _looks_like_structured_vertical_columns

def _align_vertical_lines_to_detector_block(
    lines: list[list[int]],
    block_box: list[int],
) -> list[list[int]]:
    if not lines:
        return lines

    _, block_top, _, block_bottom = [int(v) for v in block_box]
    block_height = max(1, block_bottom - block_top)
    vertical_count = len(lines)
    aligned: list[list[int]] = []
    for line in lines:
        box = list(_line_axis_box(line))
        if box[1] < block_top:
            box[1] = block_top

        line_height = max(1, box[3] - box[1])
        top_gap = max(0, box[1] - block_top)
        bottom_gap = max(0, block_bottom - box[3])
        if line_height >= block_height * 0.65 and top_gap <= block_height * 0.25:
            box[1] = block_top
            top_gap = 0

        if vertical_count <= 4 and line_height >= block_height * 0.40 and top_gap <= block_height * 0.12:
            box[1] = block_top

        if vertical_count <= 3 and line_height >= block_height * 0.70 and bottom_gap <= block_height * 0.20:
            box[3] = block_bottom

        aligned.append(box)

    return aligned

def _trim_disconnected_vertical_line_tails(
    lines: list[list[int]],
    text_mask: np.ndarray,
    mask_stats,
) -> list[list[int]]:
    if not lines:
        return lines

    height, width = text_mask.shape[:2]
    median_h = max(1.0, float(getattr(mask_stats, "median_h", 1.0)))
    gap_limit = max(24, int(round(median_h * 1.5)))
    tail_gap_limit = max(72, int(round(median_h * 3.0)))
    min_trim = max(18, int(round(median_h * 0.85)))

    trimmed_lines: list[list[int]] = []
    for line in lines:
        x1, y1, x2, y2 = _line_axis_box(line)
        x1 = max(0, min(width - 1, x1))
        x2 = max(0, min(width - 1, x2))
        y1 = max(0, min(height - 1, y1))
        y2 = max(0, min(height - 1, y2))
        if x2 < x1 or y2 < y1:
            trimmed_lines.append(line)
            continue

        region = text_mask[y1 : y2 + 1, x1 : x2 + 1]
        row_pixels = region.sum(axis=1)
        active_rows = np.flatnonzero(row_pixels > 0)
        if active_rows.size <= 1:
            trimmed_lines.append(line)
            continue

        groups: list[tuple[int, int, int]] = []
        group_start = int(active_rows[0])
        previous = int(active_rows[0])
        for row in active_rows[1:]:
            row_int = int(row)
            if row_int - previous > gap_limit:
                groups.append((y1 + group_start, y1 + previous, int(row_pixels[group_start : previous + 1].sum())))
                group_start = row_int
            previous = row_int
        groups.append((y1 + group_start, y1 + previous, int(row_pixels[group_start : previous + 1].sum())))

        if len(groups) <= 1:
            trimmed_lines.append(line)
            continue

        main_index = max(range(len(groups)), key=lambda index: groups[index][2])
        main_pixels = max(1, groups[main_index][2])
        selected_end = groups[main_index][1]
        cut_tail = False
        cut_gap = 0
        for group_start_y, group_end_y, group_pixels in groups[main_index + 1 :]:
            gap = group_start_y - selected_end - 1
            group_height = group_end_y - group_start_y + 1
            weak_tail = group_pixels <= main_pixels * 0.75
            tiny_tail = group_pixels <= main_pixels * 0.20 or group_height <= max(8.0, median_h * 0.75)
            if gap >= tail_gap_limit and (weak_tail or tiny_tail):
                cut_tail = True
                cut_gap = gap
                break
            selected_end = group_end_y

        if cut_tail:
            line_width = max(1, x2 - x1 + 1)
            slack_limit = max(18.0, min(96.0, median_h * 2.5, line_width * 1.75, cut_gap * 0.35))
            selected_end = min(y2, selected_end + int(round(min(max(0, cut_gap - 1), slack_limit))))

        kept_height = selected_end - y1 + 1
        original_height = y2 - y1 + 1
        main_height = groups[main_index][1] - groups[main_index][0] + 1
        if (
            not cut_tail
            or y2 - selected_end < min_trim
            or main_height < max(36.0, median_h * 1.75)
            or kept_height < original_height * 0.55
        ):
            trimmed_lines.append(line)
            continue

        selected_region = text_mask[y1 : selected_end + 1, x1 : x2 + 1]
        bounds = _mask_bounds(selected_region)
        if bounds is None:
            trimmed_lines.append([x1, y1, x2, selected_end])
            continue

        bound_x1, _, bound_x2, bound_y2 = bounds
        trimmed_lines.append([x1 + bound_x1, y1, x1 + bound_x2, y1 + bound_y2])

    return trimmed_lines

def _drop_nested_vertical_line_duplicates(lines: list[list[int]]) -> list[list[int]]:
    if len(lines) <= 1:
        return lines

    boxes = [_line_axis_box(line) for line in lines]
    keep: list[list[int]] = []
    for index, (line, box) in enumerate(zip(lines, boxes)):
        box_width = max(1, box[2] - box[0] + 1)
        box_height = max(1, box[3] - box[1] + 1)
        nested_duplicate = False
        for other_index, other in enumerate(boxes):
            if index == other_index:
                continue
            other_width = max(1, other[2] - other[0] + 1)
            other_height = max(1, other[3] - other[1] + 1)
            if other_width < box_width * 1.75 or other_height < box_height * 1.10:
                continue

            overlap_x = min(box[2], other[2]) - max(box[0], other[0]) + 1
            overlap_y = min(box[3], other[3]) - max(box[1], other[1]) + 1
            if overlap_x >= box_width * 0.70 and overlap_y >= box_height * 0.85:
                nested_duplicate = True
                break

        if not nested_duplicate:
            keep.append(line)

    return keep

def _widen_skinny_vertical_lines_by_spacing(
    lines: list[list[int]],
    width: int,
    mask_stats,
) -> list[list[int]]:
    if len(lines) < 2 or len(lines) > 6:
        return lines

    boxes = [_line_axis_box(line) for line in lines]
    line_widths = np.array([max(1, box[2] - box[0] + 1) for box in boxes], dtype=float)
    if line_widths.size == 0:
        return lines

    median_line_width = float(np.median(line_widths))
    median_h = max(1.0, float(getattr(mask_stats, "median_h", 1.0)))
    indexed_boxes = sorted(enumerate(boxes), key=lambda item: (item[1][0] + item[1][2]) / 2.0)
    centers = {
        index: (box[0] + box[2]) / 2.0
        for index, box in enumerate(boxes)
    }

    widened = [list(line) for line in lines]
    for sorted_index, (line_index, box) in enumerate(indexed_boxes):
        x1, y1, x2, y2 = box
        line_width = max(1, x2 - x1 + 1)
        line_height = max(1, y2 - y1 + 1)
        if line_width > 44:
            continue
        if line_width >= median_line_width * 0.82:
            continue
        if line_height < max(180.0, median_h * 12.0, line_width * 8.0):
            continue

        center = centers[line_index]
        desired_width = min(line_width + 40.0, max(48.0, median_line_width * 1.45, line_width * 1.60))
        desired_left = int(math.floor(center - desired_width / 2.0))
        desired_right = int(math.ceil(center + desired_width / 2.0))

        left_limit = 0
        if sorted_index > 0:
            prev_index, _ = indexed_boxes[sorted_index - 1]
            left_limit = int(math.floor((centers[prev_index] + center) / 2.0)) + 1

        right_limit = width - 1
        if sorted_index + 1 < len(indexed_boxes):
            next_index, _ = indexed_boxes[sorted_index + 1]
            right_limit = int(math.ceil((center + centers[next_index]) / 2.0)) - 1

        new_x1 = min(x1, max(0, left_limit, desired_left))
        new_x2 = max(x2, min(width - 1, right_limit, desired_right))
        if new_x2 <= new_x1:
            continue
        widened[line_index] = [new_x1, y1, new_x2, y2]

    return widened

def _split_tall_vertical_lines_on_valleys(
    lines: list[list[int]],
    text_mask: np.ndarray,
    mask_stats,
) -> list[list[int]]:
    if len(lines) > 4:
        return lines

    boxes = [_line_axis_box(line) for line in lines]
    widths = np.array([max(1, box[2] - box[0] + 1) for box in boxes], dtype=float)
    if widths.size == 0:
        return lines

    median_width = float(np.median(widths))
    median_h = max(1.0, float(getattr(mask_stats, "median_h", 1.0)))
    split_lines: list[list[int]] = []
    for box in boxes:
        x1, y1, x2, y2 = box
        box_width = max(1, x2 - x1 + 1)
        box_height = max(1, y2 - y1 + 1)
        if box_width < max(56.0, median_width * 1.25):
            split_lines.append(box)
            continue
        if box_height < max(420.0, median_h * 18.0, box_width * 4.0):
            split_lines.append(box)
            continue

        region = text_mask[y1 : y2 + 1, x1 : x2 + 1]
        row_pixels = region.sum(axis=1).astype(float)
        if row_pixels.size < 80 or row_pixels.max() <= 0:
            split_lines.append(box)
            continue

        window = max(9, int(round(median_h * 0.75)))
        if window % 2 == 0:
            window += 1
        smooth_rows = np.convolve(row_pixels, np.ones(window, dtype=float) / window, mode="same")
        valley_threshold = max(1.0, float(smooth_rows.max()) * 0.20)
        edge_margin = max(20, int(round(box_height * 0.08)))

        low_rows = np.flatnonzero(smooth_rows <= valley_threshold)
        valley_runs: list[tuple[int, int, float]] = []
        if low_rows.size:
            run_start = int(low_rows[0])
            previous = int(low_rows[0])
            for row in low_rows[1:]:
                row_int = int(row)
                if row_int - previous > 1:
                    valley_runs.append((run_start, previous, float(smooth_rows[run_start : previous + 1].mean())))
                    run_start = row_int
                previous = row_int
            valley_runs.append((run_start, previous, float(smooth_rows[run_start : previous + 1].mean())))

        min_valley_len = max(12, int(round(median_h * 0.6)))
        valley_runs = [
            run for run in valley_runs
            if run[0] >= edge_margin and run[1] <= row_pixels.size - 1 - edge_margin and (run[1] - run[0] + 1) >= min_valley_len
        ]
        if not valley_runs:
            split_lines.append(box)
            continue

        best_split: tuple[list[int], list[int]] | None = None
        best_score: tuple[float, float, float, float] | None = None
        for run_start, run_end, mean_valley in valley_runs:
            split_row = int(round((run_start + run_end) / 2.0))
            upper_region = region[:split_row, :]
            lower_region = region[split_row + 1 :, :]
            upper_bounds = _mask_bounds(upper_region) if upper_region.size else None
            lower_bounds = _mask_bounds(lower_region) if lower_region.size else None
            if upper_bounds is None or lower_bounds is None:
                continue

            upper_box = [x1 + upper_bounds[0], y1 + upper_bounds[1], x1 + upper_bounds[2], y1 + upper_bounds[3]]
            lower_box = [
                x1 + lower_bounds[0],
                y1 + split_row + 1 + lower_bounds[1],
                x1 + lower_bounds[2],
                y1 + split_row + 1 + lower_bounds[3],
            ]
            upper_height = max(1, upper_box[3] - upper_box[1] + 1)
            lower_height = max(1, lower_box[3] - lower_box[1] + 1)
            min_side_height = max(100.0, box_width * 1.2, median_h * 4.0)
            if upper_height < min_side_height or lower_height < min_side_height:
                continue

            upper_peak = float(smooth_rows[:run_start].max()) if run_start > 0 else 0.0
            lower_peak = float(smooth_rows[run_end + 1 :].max()) if run_end + 1 < smooth_rows.size else 0.0
            max_peak = float(smooth_rows.max())
            if upper_peak < max_peak * 0.35 or lower_peak < max_peak * 0.35:
                continue

            balance = min(upper_height, lower_height) / max(upper_height, lower_height)
            score = (balance, -mean_valley, min(upper_peak, lower_peak), float(-(run_end - run_start + 1)))
            if best_score is None or score > best_score:
                best_score = score
                best_split = (upper_box, lower_box)

        if best_split is None:
            split_lines.append(box)
            continue

        split_lines.extend(best_split)

    return split_lines

def _merge_fragmented_top_edge_vertical_lines(
    lines: list[list[int]],
    text_mask: np.ndarray,
    mask_stats,
) -> list[list[int]]:
    if len(lines) < 6 or len(lines) > 12:
        return lines

    height, _ = text_mask.shape[:2]
    boxes = sorted((_line_axis_box(line) for line in lines), key=lambda box: box[0])
    widths = np.array([max(1, box[2] - box[0] + 1) for box in boxes], dtype=float)
    if widths.size == 0:
        return lines

    median_width = float(np.median(widths))
    top_limit = max(6, int(round(height * 0.05)))
    merged_lines: list[list[int]] = []
    index = 0
    while index < len(boxes):
        current = boxes[index]
        merged: list[int] | None = None

        if index + 1 < len(boxes):
            candidate = boxes[index + 1]
            merged = _merge_top_aligned_vertical_pair(current, candidate, text_mask, median_width, top_limit)
            if merged is not None:
                merged_lines.append(merged)
                index += 2
                continue

        if index + 1 < len(boxes):
            candidate = boxes[index + 1]
            merged = _merge_top_edge_fragment_into_neighbor(current, candidate, text_mask, median_width, top_limit, height)
            if merged is not None:
                merged_lines.append(merged)
                index += 2
                continue

        merged_lines.append(current)
        index += 1

    return merged_lines

def _repair_fragmented_vertical_blocks_with_raw_support(
    lines: list[list[int]],
    raw_vertical_lines: list[list[int]],
    text_mask: np.ndarray,
    mask_stats,
) -> list[list[int]]:
    if len(lines) < 5 or len(lines) > 10:
        return lines
    if len(raw_vertical_lines) < len(lines) + 4:
        return lines

    height, width = text_mask.shape[:2]
    top_limit = max(6, int(round(height * 0.05)))
    boxes = sorted((_line_axis_box(line) for line in lines), key=lambda box: box[0])
    top_count = sum(1 for box in boxes if box[1] <= top_limit)
    if top_count < max(3, len(boxes) // 2):
        return lines

    median_h = max(1.0, float(getattr(mask_stats, "median_h", 1.0)))
    gap_limit = max(24, int(round(median_h * 1.5)))
    grown_boxes: list[list[int]] = []
    for box in boxes:
        lower_dominant = _lower_dominant_vertical_group_box(box, text_mask, gap_limit, top_limit, median_h)
        if lower_dominant is not None:
            grown_boxes.append(_pad_line_boxes([lower_dominant], "vertical", width, height)[0])
        else:
            grown_boxes.append(box)

    non_top_bottoms = [box[3] for box in grown_boxes if box[1] > top_limit]
    bottom_cap = max(non_top_bottoms) if non_top_bottoms else None
    adjusted_boxes: list[list[int]] = []
    for box in grown_boxes:
        aligned_raw_boxes = _aligned_raw_vertical_support_boxes(box, raw_vertical_lines)
        if not aligned_raw_boxes:
            adjusted_boxes.append(box)
            continue

        raw_top = min(raw_box[1] for raw_box in aligned_raw_boxes)
        raw_bottom = max(raw_box[3] for raw_box in aligned_raw_boxes)
        top_extension_limit = max(20, int(round(median_h * 2.0)))
        bottom_extension_limit = max(80, int(round(median_h * 6.0)))
        if box[1] > top_limit and raw_top + top_extension_limit < box[1]:
            adjusted_boxes.append([box[0], raw_top, box[2], box[3]])
            continue
        if (
            box[1] <= top_limit
            and bottom_cap is not None
            and box[3] < bottom_cap - bottom_extension_limit
            and raw_bottom > box[3] + bottom_extension_limit
        ):
            adjusted_boxes.append([box[0], box[1], box[2], min(raw_bottom, bottom_cap)])
            continue
        adjusted_boxes.append(box)

    kept_boxes: list[list[int]] = []
    for index, box in enumerate(adjusted_boxes):
        box_width = max(1, box[2] - box[0] + 1)
        box_height = max(1, box[3] - box[1] + 1)
        aligned_raw_boxes = _aligned_raw_vertical_support_boxes(box, raw_vertical_lines)
        raw_bottom = max((raw_box[3] for raw_box in aligned_raw_boxes), default=box[3])
        should_drop = False
        if (
            box[1] <= top_limit
            and box_height <= max(300.0, height * 0.24)
            and raw_bottom <= box[3] + max(24, int(round(median_h * 2.0)))
            and index + 1 < len(adjusted_boxes)
        ):
            next_box = adjusted_boxes[index + 1]
            next_height = max(1, next_box[3] - next_box[1] + 1)
            gap_x = next_box[0] - box[2] - 1
            if gap_x <= max(14, int(round(box_width * 0.25))) and next_height >= box_height * 2.8:
                should_drop = True

        if not should_drop:
            kept_boxes.append(box)

    return kept_boxes

def _lower_dominant_vertical_group_box(
    box: list[int],
    text_mask: np.ndarray,
    gap_limit: int,
    top_limit: int,
    median_h: float,
) -> list[int] | None:
    if box[1] <= top_limit:
        return None

    groups = _row_groups_in_vertical_box(text_mask, box, gap_limit)
    if len(groups) < 2:
        return None

    first_group = groups[0]
    last_group = groups[-1]
    gap_y = last_group[0] - first_group[1] - 1
    if gap_y < max(72, int(round(median_h * 3.0))):
        return None
    if last_group[2] < first_group[2] * 1.8:
        return None

    region = text_mask[last_group[0] : last_group[1] + 1, box[0] : box[2] + 1]
    bounds = _mask_bounds(region)
    if bounds is None:
        return None
    return [box[0] + bounds[0], last_group[0] + bounds[1], box[0] + bounds[2], last_group[0] + bounds[3]]

def _aligned_raw_vertical_support_boxes(
    box: list[int],
    raw_vertical_lines: list[list[int]],
) -> list[list[int]]:
    aligned: list[list[int]] = []
    box_width = max(1, box[2] - box[0] + 1)
    box_center = (box[0] + box[2]) / 2.0
    for raw_box in raw_vertical_lines:
        raw_width = max(1, raw_box[2] - raw_box[0] + 1)
        overlap_x = min(box[2], raw_box[2]) - max(box[0], raw_box[0]) + 1
        raw_center = (raw_box[0] + raw_box[2]) / 2.0
        if overlap_x >= min(box_width, raw_width) * 0.35 or abs(raw_center - box_center) <= max(10.0, box_width * 0.30):
            aligned.append(raw_box)
    return aligned

def _row_groups_in_vertical_box(
    text_mask: np.ndarray,
    box: list[int],
    gap_limit: int,
) -> list[tuple[int, int, int]]:
    x1, y1, x2, y2 = box
    region = text_mask[y1 : y2 + 1, x1 : x2 + 1]
    row_pixels = region.sum(axis=1)
    active_rows = np.flatnonzero(row_pixels > 0)
    if active_rows.size == 0:
        return []

    groups: list[tuple[int, int, int]] = []
    group_start = int(active_rows[0])
    previous = int(active_rows[0])
    for row in active_rows[1:]:
        row_int = int(row)
        if row_int - previous > gap_limit:
            groups.append((y1 + group_start, y1 + previous, int(row_pixels[group_start : previous + 1].sum())))
            group_start = row_int
        previous = row_int
    groups.append((y1 + group_start, y1 + previous, int(row_pixels[group_start : previous + 1].sum())))
    return groups

def _merge_top_aligned_vertical_pair(
    current: list[int],
    candidate: list[int],
    text_mask: np.ndarray,
    median_width: float,
    top_limit: int,
) -> list[int] | None:
    current_width = max(1, current[2] - current[0] + 1)
    candidate_width = max(1, candidate[2] - candidate[0] + 1)
    current_height = max(1, current[3] - current[1] + 1)
    candidate_height = max(1, candidate[3] - candidate[1] + 1)
    gap = candidate[0] - current[2] - 1
    overlap_x = min(current[2], candidate[2]) - max(current[0], candidate[0]) + 1

    both_top_aligned = current[1] <= top_limit and candidate[1] <= top_limit
    similar_height = min(current_height, candidate_height) >= max(current_height, candidate_height) * 0.45
    touching = gap <= max(2, int(round(median_width * 0.10))) or overlap_x > 0
    moderate_width = max(current_width, candidate_width) <= max(90.0, median_width * 4.5)
    substantial_pair = overlap_x > 0 or min(current_width, candidate_width) >= median_width * 1.4
    if not (both_top_aligned and similar_height and touching and moderate_width and substantial_pair):
        return None

    return _merged_vertical_pair_bounds(current, candidate, text_mask)

def _merge_top_edge_fragment_into_neighbor(
    current: list[int],
    candidate: list[int],
    text_mask: np.ndarray,
    median_width: float,
    top_limit: int,
    height: int,
) -> list[int] | None:
    current_width = max(1, current[2] - current[0] + 1)
    current_height = max(1, current[3] - current[1] + 1)
    candidate_height = max(1, candidate[3] - candidate[1] + 1)
    gap = candidate[0] - current[2] - 1

    is_small_top_fragment = (
        current[1] <= top_limit
        and current_width <= max(24.0, median_width * 0.8)
        and current_height <= max(height * 0.30, 260.0)
    )
    is_tall_neighbor = candidate_height >= max(current_height * 2.0, height * 0.45)
    if not (is_small_top_fragment and is_tall_neighbor):
        return None
    if gap > max(14, int(round(median_width * 0.8))):
        return None

    return _merged_vertical_pair_bounds(current, candidate, text_mask)

def _merged_vertical_pair_bounds(
    left: list[int],
    right: list[int],
    text_mask: np.ndarray,
) -> list[int] | None:
    x1 = min(left[0], right[0])
    y1 = min(left[1], right[1])
    x2 = max(left[2], right[2])
    y2 = max(left[3], right[3])
    region = text_mask[y1 : y2 + 1, x1 : x2 + 1]
    bounds = _mask_bounds(region)
    if bounds is None:
        return None
    return [x1 + bounds[0], y1 + bounds[1], x1 + bounds[2], y1 + bounds[3]]

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
