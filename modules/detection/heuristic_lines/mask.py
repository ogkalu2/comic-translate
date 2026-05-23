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
