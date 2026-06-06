from __future__ import annotations
from dataclasses import dataclass
import numpy as np
import imkit as imk

@dataclass(slots=True)
class _MaskStats:
    mask: np.ndarray
    mask_uint8: np.ndarray
    total_pixels: int
    integral_image: np.ndarray
    num_labels: int
    labels: np.ndarray
    stats: np.ndarray
    centroids: np.ndarray
    median_w: float
    median_h: float
    component_boxes: list[dict[str, float]]

@dataclass(slots=True)
class _ConnectedComponents:
    mask_uint8: np.ndarray
    num_labels: int
    labels: np.ndarray
    stats: np.ndarray
    centroids: np.ndarray

def _compute_integral_image(mask: np.ndarray) -> np.ndarray:
    return mask.astype(np.int32, copy=False).cumsum(axis=0).cumsum(axis=1)

def _sum_box_pixels(integral_image: np.ndarray, x1: int, y1: int, x2: int, y2: int) -> int:
    total = int(integral_image[y2, x2])
    if x1 > 0:
        total -= int(integral_image[y2, x1 - 1])
    if y1 > 0:
        total -= int(integral_image[y1 - 1, x2])
    if x1 > 0 and y1 > 0:
        total += int(integral_image[y1 - 1, x1 - 1])
    return total

def _mask_bounds(mask: np.ndarray) -> tuple[int, int, int, int] | None:
    if mask.size == 0:
        return None
    row_has_ink = mask.any(axis=1)
    if not bool(row_has_ink.any()):
        return None
    col_has_ink = mask.any(axis=0)
    y1 = int(np.argmax(row_has_ink))
    y2 = int(row_has_ink.size - np.argmax(row_has_ink[::-1]) - 1)
    x1 = int(np.argmax(col_has_ink))
    x2 = int(col_has_ink.size - np.argmax(col_has_ink[::-1]) - 1)
    return x1, y1, x2, y2

def _component_boxes_from_cc(
    stats: np.ndarray,
    centroids: np.ndarray,
    min_area: int = 20,
) -> list[dict[str, float]]:
    components: list[dict[str, float]] = []
    for label in range(1, stats.shape[0]):
        x1, y1, comp_width, comp_height, area = [int(v) for v in stats[label]]
        if area < min_area:
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

def _compute_connected_components(mask: np.ndarray) -> _ConnectedComponents:
    mask_uint8 = mask.astype(np.uint8)
    num_labels, labels, stats, centroids = imk.connected_components_with_stats(
        mask_uint8,
        connectivity=8,
    )
    return _ConnectedComponents(
        mask_uint8=mask_uint8,
        num_labels=num_labels,
        labels=labels,
        stats=stats,
        centroids=centroids,
    )

def _component_medians(stats: np.ndarray) -> tuple[float, float]:
    valid_stats = stats[1:][stats[1:, 4] >= 8] if stats.shape[0] > 1 else np.empty((0, 5), dtype=stats.dtype)
    if valid_stats.size > 0:
        return float(np.median(valid_stats[:, 2])), float(np.median(valid_stats[:, 3]))
    return 12.0, 12.0

def _compute_mask_stats(mask: np.ndarray) -> _MaskStats:
    cc = _compute_connected_components(mask)
    median_w, median_h = _component_medians(cc.stats)

    return _MaskStats(
        mask=mask,
        mask_uint8=cc.mask_uint8,
        total_pixels=int(mask.sum()),
        integral_image=_compute_integral_image(mask),
        num_labels=cc.num_labels,
        labels=cc.labels,
        stats=cc.stats,
        centroids=cc.centroids,
        median_w=median_w,
        median_h=median_h,
        component_boxes=_component_boxes_from_cc(cc.stats, cc.centroids),
    )

def _prepare_text_mask(image: np.ndarray) -> np.ndarray | None:
    text_mask = _text_mask(image)
    if text_mask is None:
        return None
    return _remove_non_text_components(_remove_edge_components(text_mask))

def _prepare_inverse_text_mask(image: np.ndarray) -> np.ndarray | None:
    text_mask = _inverse_text_mask(image)
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

def _inverse_text_mask(image: np.ndarray) -> np.ndarray | None:
    if image is None or image.size == 0:
        return None
    gray = imk.to_gray(image)
    threshold, _ = imk.otsu_threshold(gray)
    histogram = np.bincount(gray.reshape(-1), minlength=256)
    fg_pixels = int(histogram[: int(threshold)].sum())
    bg_is_light = fg_pixels < (gray.size * 0.5)
    return gray >= threshold if bg_is_light else gray <= threshold

def _remove_edge_components(text_mask: np.ndarray) -> np.ndarray:
    cc = _compute_connected_components(text_mask)
    num_labels = cc.num_labels
    labels = cc.labels
    stats = cc.stats
    if num_labels <= 1:
        return text_mask

    height, width = text_mask.shape[:2]
    cleaned = text_mask.copy()
    original_pixels = int(text_mask.sum())
    median_w, median_h = _component_medians(stats)

    removed_labels: list[int] = []

    # 2. Decide which components to remove
    for label in range(1, num_labels):
        x1, y1, comp_width, comp_height, area = [int(v) for v in stats[label]]
        x2 = x1 + comp_width - 1
        y2 = y1 + comp_height - 1

        # Check if it touches any edge (allow up to 5 pixels from the border)
        touches_left = (x1 <= 5)
        touches_right = (x2 >= width - 6)
        touches_top = (y1 <= 5)
        touches_bottom = (y2 >= height - 6)

        touches_edge = touches_left or touches_right or touches_top or touches_bottom
        if not touches_edge:
            continue

        # If it touches left or right edge, it is almost certainly a bubble/panel border.
        # We always remove it.
        if touches_left or touches_right:
            cleaned[labels == label] = False
            removed_labels.append(label)
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

        # Allow horizontally merged text lines (which touch top/bottom edges)
        # if their height is characteristic of a standard single line.
        is_merged_horizontal_line = (
            comp_height <= max(1.8 * median_h, 12.0) and
            comp_width <= max(8.0 * median_w, width * 0.85, 80.0)
        )

        is_character = (is_small_crop_relative or is_small_median_relative or is_merged_horizontal_line) and not is_too_small_noise

        if not is_character:
            cleaned[labels == label] = False
            removed_labels.append(label)

    if int(cleaned.sum()) < max(8, original_pixels * 0.25) and not _has_enough_text_after_edge_cleanup(cleaned):
        return text_mask
    return _restore_leading_text_from_edge_components(text_mask, cleaned, labels, removed_labels, median_w, median_h)

def _has_enough_text_after_edge_cleanup(cleaned_mask: np.ndarray) -> bool:
    remaining_pixels = int(cleaned_mask.sum())
    if remaining_pixels < 200:
        return False

    cc = _compute_connected_components(cleaned_mask)
    text_like_components = 0
    for label in range(1, cc.num_labels):
        _, _, comp_width, comp_height, area = [int(v) for v in cc.stats[label]]
        if area < 8:
            continue
        if comp_width < 2 or comp_height < 2:
            continue
        text_like_components += 1

    return text_like_components >= 4

def _restore_leading_text_from_edge_components(
    original_mask: np.ndarray,
    cleaned_mask: np.ndarray,
    labels: np.ndarray,
    removed_labels: list[int],
    median_w: float,
    median_h: float,
) -> np.ndarray:
    if not removed_labels or not bool(cleaned_mask.any()):
        return cleaned_mask

    height, width = cleaned_mask.shape[:2]
    row_spans = _horizontal_ink_spans(cleaned_mask)
    if not row_spans:
        return cleaned_mask
    if len(row_spans) > 4 or height > max(100, int(round(median_h * 8.0))):
        return cleaned_mask

    restored = cleaned_mask.copy()
    for sy1, sy2 in row_spans:
        band_y1 = max(0, sy1 - max(2, int(round(median_h * 0.25))))
        band_y2 = min(height, sy2 + max(2, int(round(median_h * 0.25))))
        cleaned_band = cleaned_mask[band_y1:band_y2, :]
        text_x1 = _band_text_min_x(cleaned_band)
        if text_x1 is None:
            continue

        if text_x1 <= max(2, int(round(median_w * 0.5))):
            continue

        side_mask = np.zeros_like(cleaned_mask)
        for label in removed_labels:
            side_mask[band_y1:band_y2, :text_x1] |= (labels[band_y1:band_y2, :text_x1] == label)

        side_mask = _remove_long_edge_strokes(side_mask, band_y1, band_y2)
        if not bool(side_mask.any()):
            continue

        candidate = _leading_text_candidate(side_mask, text_x1, median_w, median_h)
        if candidate is not None:
            restored |= candidate

    return restored

def _band_text_min_x(band_mask: np.ndarray) -> int | None:
    band_stats = _compute_mask_stats(band_mask)
    min_x: int | None = None
    for label in range(1, band_stats.num_labels):
        x1, _, comp_width, comp_height, area = [int(v) for v in band_stats.stats[label]]
        if area < 8 or comp_width < 3 or comp_height < 3:
            continue
        min_x = x1 if min_x is None else min(min_x, x1)
    return min_x

def _horizontal_ink_spans(mask: np.ndarray) -> list[tuple[int, int]]:
    height, width = mask.shape[:2]
    y_sum = mask.sum(axis=1)
    tolerance = max(1, int(width * 0.02))
    spans: list[tuple[int, int]] = []
    start = -1
    for y in range(height):
        if int(y_sum[y]) > tolerance:
            if start == -1:
                start = y
        elif start != -1:
            spans.append((start, y))
            start = -1
    if start != -1:
        spans.append((start, height))
    return spans

def _remove_long_edge_strokes(mask: np.ndarray, band_y1: int, band_y2: int) -> np.ndarray:
    cleaned = mask.copy()
    band_height = max(1, band_y2 - band_y1)
    bounds = _mask_bounds(cleaned)
    active_width = (bounds[2] - bounds[0] + 1) if bounds is not None else cleaned.shape[1]
    row_sum = cleaned.sum(axis=1)
    col_sum = cleaned.sum(axis=0)
    cleaned[row_sum >= max(20, int(active_width * 0.30)), :] = False
    cleaned[:, col_sum >= max(30, int(band_height * 1.25))] = False
    if int(cleaned.sum()) < max(8, int(mask.sum() * 0.20)):
        return mask
    return cleaned

def _leading_text_candidate(
    side_mask: np.ndarray,
    text_x1: int,
    median_w: float,
    median_h: float,
) -> np.ndarray | None:
    side_stats = _compute_mask_stats(side_mask)
    if side_stats.num_labels <= 1:
        return None

    kept = np.zeros_like(side_mask)
    for label in range(1, side_stats.num_labels):
        x1, y1, comp_width, comp_height, area = [int(v) for v in side_stats.stats[label]]
        x2 = x1 + comp_width - 1
        if area < 8:
            continue
        if x2 >= text_x1:
            continue
        if comp_height < max(3, int(round(median_h * 0.25))):
            continue
        if comp_height > max(18, int(round(median_h * 2.2))):
            continue
        if comp_width > max(40, int(round(median_w * 5.0))):
            continue
        kept[side_stats.labels == label] = True

    if not bool(kept.any()):
        return None

    kept = _select_rightmost_leading_text_cluster(kept, text_x1, median_w, median_h)
    if kept is None:
        return None

    bounds = _mask_bounds(kept)
    if bounds is None:
        return None
    gap_to_text = text_x1 - bounds[2] - 1
    candidate_width = bounds[2] - bounds[0] + 1
    if gap_to_text > max(12, int(round(median_w * 2.5))):
        return None
    if candidate_width > max(90, int(round(median_w * 7.0))):
        return None

    return kept

def _select_rightmost_leading_text_cluster(
    mask: np.ndarray,
    text_x1: int,
    median_w: float,
    median_h: float,
) -> np.ndarray | None:
    mask_stats = _compute_mask_stats(mask)
    if mask_stats.num_labels <= 1:
        return None

    components: list[dict[str, int]] = []
    for label in range(1, mask_stats.num_labels):
        x1, y1, comp_width, comp_height, area = [int(v) for v in mask_stats.stats[label]]
        x2 = x1 + comp_width - 1
        y2 = y1 + comp_height - 1
        if area < 8 or x2 >= text_x1:
            continue
        components.append({
            "label": label,
            "x1": x1,
            "y1": y1,
            "x2": x2,
            "y2": y2,
            "width": comp_width,
            "height": comp_height,
            "area": area,
        })

    if not components:
        return None

    components.sort(key=lambda item: item["x1"])
    groups: list[list[dict[str, int]]] = [[components[0]]]
    group_max_x2s: list[int] = [components[0]["x2"]]
    max_gap = max(4, int(round(median_w * 0.75)))
    for component in components[1:]:
        current_x2 = group_max_x2s[-1]
        if component["x1"] - current_x2 - 1 <= max_gap:
            groups[-1].append(component)
            group_max_x2s[-1] = max(group_max_x2s[-1], component["x2"])
        else:
            groups.append([component])
            group_max_x2s.append(component["x2"])

    best_group: list[dict[str, int]] | None = None
    best_x2 = -1
    for group in groups:
        group_x1 = min(item["x1"] for item in group)
        group_x2 = max(item["x2"] for item in group)
        group_y1 = min(item["y1"] for item in group)
        group_y2 = max(item["y2"] for item in group)
        group_width = group_x2 - group_x1 + 1
        group_height = group_y2 - group_y1 + 1
        gap_to_text = text_x1 - group_x2 - 1
        if gap_to_text > max(12, int(round(median_w * 2.5))):
            continue
        if group_width < max(10, int(round(median_w * 0.60))):
            continue
        if group_height < max(4, int(round(median_h * 0.25))):
            continue
        if group_x2 > best_x2:
            best_x2 = group_x2
            best_group = group

    if best_group is None:
        return None

    selected = np.zeros_like(mask)
    for component in best_group:
        selected[mask_stats.labels == component["label"]] = True
    return selected

def _remove_non_text_components(text_mask: np.ndarray) -> np.ndarray:
    cc = _compute_connected_components(text_mask)
    if cc.num_labels <= 1:
        return text_mask

    height, width = text_mask.shape[:2]
    cleaned = text_mask.copy()
    original_pixels = int(text_mask.sum())
    for label in range(1, cc.num_labels):
        x1, y1, comp_width, comp_height, area = [int(v) for v in cc.stats[label]]
        component_density = area / max(1, comp_width * comp_height)
        if comp_width >= width * 0.55 and comp_height >= height * 0.35 and component_density < 0.08:
            cleaned[cc.labels == label] = False

    if int(cleaned.sum()) < max(8, original_pixels * 0.20):
        return text_mask
    return cleaned

def _filter_vertical_columns_in_horizontal_block(mask: np.ndarray) -> np.ndarray:
    h, w = mask.shape[:2]
    x_sum = mask.sum(axis=0)
    
    # Gap threshold: very low ink count
    tolerance_x = max(1, int(h * 0.02))
    
    # Find columns (spans in x)
    columns = []
    start_x = -1
    for x in range(w):
        if int(x_sum[x]) > tolerance_x:
            if start_x == -1:
                start_x = x
        elif start_x != -1:
            columns.append((start_x, x))
            start_x = -1
    if start_x != -1:
        columns.append((start_x, w))
        
    if len(columns) <= 1:
        return mask
        
    column_pixels = []
    for cx1, cx2 in columns:
        col_mask = mask[:, cx1:cx2]
        column_pixels.append(int(col_mask.sum()))
        
    # Find the main column (the one with the maximum pixels)
    max_idx = int(np.argmax(column_pixels))
    max_pixels = column_pixels[max_idx]
    
    # Check if the main column dominates (e.g. contains >= 70% of the total pixels)
    total_pixels = sum(column_pixels)
    if max_pixels >= total_pixels * 0.70:
        filtered_mask = mask.copy()
        cx1, cx2 = columns[max_idx]
        filtered_mask[:, :cx1] = False
        filtered_mask[:, cx2:] = False
        return filtered_mask
        
    return mask

def _check_alignment(lines_a, lines_b):
    from .geometry import _line_axis_box
    aligned_count = 0
    for la in lines_a:
        lax1, lay1, lax2, lay2 = _line_axis_box(la)
        la_h = lay2 - lay1 + 1
        
        best_overlap = 0
        best_lb_h = 1
        best_lb_center_y = None
        for lb in lines_b:
            lbx1, lby1, lbx2, lby2 = _line_axis_box(lb)
            lb_h = lby2 - lby1 + 1
            
            y_int1 = max(lay1, lby1)
            y_int2 = min(lay2, lby2)
            overlap = max(0, y_int2 - y_int1 + 1)
            if overlap > best_overlap:
                best_overlap = overlap
                best_lb_h = lb_h
                best_lb_center_y = (lby1 + lby2) / 2.0
                
        if best_overlap > 0:
            max_h = max(la_h, best_lb_h)
            if best_overlap >= 0.50 * max_h:
                aligned_count += 1
                continue

        if best_lb_center_y is None:
            for lb in lines_b:
                _, lby1, _, lby2 = _line_axis_box(lb)
                lb_center_y = (lby1 + lby2) / 2.0
                center_distance = abs((lay1 + lay2) / 2.0 - lb_center_y)
                if best_lb_center_y is None or center_distance < abs((lay1 + lay2) / 2.0 - best_lb_center_y):
                    best_lb_center_y = lb_center_y
                    best_lb_h = lby2 - lby1 + 1
        if best_lb_center_y is None:
            continue

        la_center_y = (lay1 + lay2) / 2.0
        max_h = max(la_h, best_lb_h)
        if abs(la_center_y - best_lb_center_y) <= max(4.0, max_h * 0.45):
            aligned_count += 1
                
    return aligned_count

def _split_mask_by_tall_vertical_columns(mask: np.ndarray) -> list[np.ndarray]:
    h, w = mask.shape[:2]
    x_sum = mask.sum(axis=0)
    tolerance_x = max(1, int(h * 0.02))
    
    # 1. Find vertical columns
    raw_columns = []
    start_x = -1
    for x in range(w):
        if int(x_sum[x]) > tolerance_x:
            if start_x == -1:
                start_x = x
        elif start_x != -1:
            raw_columns.append((start_x, x))
            start_x = -1
    if start_x != -1:
        raw_columns.append((start_x, w))
        
    # 2. Filter out extremely minor columns (noise)
    columns = []
    min_pixels = max(12, int(mask.sum() * 0.005))
    for cx1, cx2 in raw_columns:
        col_mask = mask[:, cx1:cx2]
        if col_mask.sum() >= min_pixels:
            columns.append((cx1, cx2))
            
    if len(columns) <= 1:
        return [mask]
        
    column_pixels = [int(mask[:, cx1:cx2].sum()) for cx1, cx2 in columns]
    total_pixels = sum(column_pixels)
    if total_pixels == 0:
        return [mask]
        
    max_idx = int(np.argmax(column_pixels))
    max_pixels = column_pixels[max_idx]
    max_ratio = max_pixels / total_pixels
    
    # Check if there is a dominant column containing >= 60% of the pixels
    if max_ratio < 0.60:
        return [mask]
        
    # 3. Compute median component height
    cc = _compute_connected_components(mask)
    valid_heights = []
    for label in range(1, cc.num_labels):
        _, _, _, comp_height, area = [int(v) for v in cc.stats[label]]
        if area >= 8:
            valid_heights.append(comp_height)
    median_h = float(np.median(valid_heights)) if valid_heights else 12.0
    
    # 4. Check if we have at least one tall non-dominant column
    has_tall_non_dominant = False
    target_non_dominant_idxs = []
    for idx, (cx1, cx2) in enumerate(columns):
        if idx == max_idx:
            continue
        col_ratio = column_pixels[idx] / total_pixels
        if col_ratio >= 0.05:  # must have at least 5% of the ink
            col_mask = mask[:, cx1:cx2]
            ys, _ = np.where(col_mask)
            if ys.size > 0:
                col_height = int(ys.max() - ys.min() + 1)
                if col_height >= 2.5 * median_h:
                    has_tall_non_dominant = True
                    target_non_dominant_idxs.append(idx)
                    
    if not has_tall_non_dominant:
        return [mask]
        
    # 5. Check Y-alignment of lines in non-dominant columns vs dominant column
    from modules.detection.heuristic_lines.clustering import _detect_lines_from_mask
    from modules.detection.heuristic_lines.skew import _filter_noise_lines
    dom_cx1, dom_cx2 = columns[max_idx]
    dom_mask = np.zeros_like(mask)
    dom_mask[:, dom_cx1:dom_cx2] = mask[:, dom_cx1:dom_cx2]
    dom_lines = _filter_noise_lines(_detect_lines_from_mask(dom_mask, "horizontal"), "horizontal")
    dom_lines = [l for l in dom_lines if l != [0, 0, w, h]]
    
    should_split = True
    for idx in target_non_dominant_idxs:
        cx1, cx2 = columns[idx]
        sub_mask = np.zeros_like(mask)
        sub_mask[:, cx1:cx2] = mask[:, cx1:cx2]
        sub_lines = _filter_noise_lines(_detect_lines_from_mask(sub_mask, "horizontal"), "horizontal")
        sub_lines = [l for l in sub_lines if l != [0, 0, w, h]]
        
        if not sub_lines:
            continue
            
        aligned_count = _check_alignment(sub_lines, dom_lines)
        if aligned_count >= 0.50 * len(sub_lines):
            should_split = False
            break
            
    if not should_split:
        return [mask]
        
    # 6. Split the mask into sub-masks
    sub_masks = []
    for cx1, cx2 in columns:
        sub_mask = np.zeros_like(mask)
        sub_mask[:, cx1:cx2] = mask[:, cx1:cx2]
        sub_masks.append(sub_mask)
    return sub_masks


