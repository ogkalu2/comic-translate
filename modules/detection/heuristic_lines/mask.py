from __future__ import annotations
import numpy as np
import imkit as imk

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

        is_character = (is_small_crop_relative or is_small_median_relative) and not is_too_small_noise

        if not is_character:
            cleaned[labels == label] = False
            removed_labels.append(label)

    if int(cleaned.sum()) < max(8, original_pixels * 0.25):
        return text_mask
    return _restore_leading_text_from_edge_components(text_mask, cleaned, labels, removed_labels, median_w, median_h)

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
    if len(row_spans) != 1 or height > max(80, int(round(median_h * 5.0))):
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
    num_labels, _, stats, _ = imk.connected_components_with_stats(
        band_mask.astype(np.uint8),
        connectivity=8,
    )
    min_x: int | None = None
    for label in range(1, num_labels):
        x1, _, comp_width, comp_height, area = [int(v) for v in stats[label]]
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
    row_sum = cleaned.sum(axis=1)
    col_sum = cleaned.sum(axis=0)
    cleaned[row_sum >= max(20, int(cleaned.shape[1] * 0.30)), :] = False
    cleaned[:, col_sum >= max(30, int(band_height * 1.25))] = False
    return cleaned

def _leading_text_candidate(
    side_mask: np.ndarray,
    text_x1: int,
    median_w: float,
    median_h: float,
) -> np.ndarray | None:
    num_labels, labels, stats, _ = imk.connected_components_with_stats(
        side_mask.astype(np.uint8),
        connectivity=8,
    )
    if num_labels <= 1:
        return None

    kept = np.zeros_like(side_mask)
    for label in range(1, num_labels):
        x1, y1, comp_width, comp_height, area = [int(v) for v in stats[label]]
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
        kept[labels == label] = True

    if not bool(kept.any()):
        return None

    ys, xs = np.where(kept)
    if xs.size == 0:
        return None
    gap_to_text = text_x1 - int(xs.max()) - 1
    candidate_width = int(xs.max() - xs.min() + 1)
    if gap_to_text > max(12, int(round(median_w * 2.5))):
        return None
    if candidate_width > max(90, int(round(median_w * 7.0))):
        return None

    return kept

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
        for lb in lines_b:
            lbx1, lby1, lbx2, lby2 = _line_axis_box(lb)
            lb_h = lby2 - lby1 + 1
            
            y_int1 = max(lay1, lby1)
            y_int2 = min(lay2, lby2)
            overlap = max(0, y_int2 - y_int1 + 1)
            if overlap > best_overlap:
                best_overlap = overlap
                best_lb_h = lb_h
                
        if best_overlap > 0:
            max_h = max(la_h, best_lb_h)
            if best_overlap >= 0.50 * max_h:
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
    num_labels, labels, stats, _ = imk.connected_components_with_stats(
        mask.astype(np.uint8),
        connectivity=8,
    )
    valid_heights = []
    for label in range(1, num_labels):
        _, _, _, comp_height, area = [int(v) for v in stats[label]]
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
    from modules.detection.heuristic_lines.skew import _detect_horizontal_lines_skew_aware
    dom_cx1, dom_cx2 = columns[max_idx]
    dom_mask = np.zeros_like(mask)
    dom_mask[:, dom_cx1:dom_cx2] = mask[:, dom_cx1:dom_cx2]
    dom_lines = _detect_horizontal_lines_skew_aware(dom_mask)
    dom_lines = [l for l in dom_lines if l != [0, 0, w, h]]
    
    should_split = True
    for idx in target_non_dominant_idxs:
        cx1, cx2 = columns[idx]
        sub_mask = np.zeros_like(mask)
        sub_mask[:, cx1:cx2] = mask[:, cx1:cx2]
        sub_lines = _detect_horizontal_lines_skew_aware(sub_mask)
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


