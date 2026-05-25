"""
Content detection and processing utilities.
"""
import numpy as np
import mahotas
from typing import Optional, Union
import imkit as imk
from modules.utils.textblock import adjust_text_line_coordinates


def filter_and_fix_bboxes(
    bboxes: Union[list, np.ndarray], 
    image_shape: Optional[tuple[int, int]] = None, 
    width_tolerance: int = 5, 
    height_tolerance: int = 5
) -> np.ndarray:
    """
    Filter out or fix bounding boxes that don't make sense.
    
    - Drops any box with x2<=x1 or y2<=y1
    - Drops any box whose width or height is <= the given tolerances
    - If image_shape is provided, clamps boxes to [0, width)×[0, height)
    
    Args:
        bboxes: array-like of boxes [[x1, y1, x2, y2], …]
        image_shape: optional tuple (img_h, img_w) to clamp coordinates into
        width_tolerance: minimum width to keep
        height_tolerance: minimum height to keep
    
    Returns:
        np.ndarray of cleaned boxes
    """
    if len(bboxes) == 0:
        return np.empty((0,4), dtype=int)

    cleaned = []
    img_h, img_w = (None, None)
    if image_shape is not None:
        img_h, img_w = image_shape[:2]

    for box in bboxes:
        x1, y1, x2, y2 = box
        
        # clamp to image if dims given
        if img_w is not None:
            x1 = max(0, min(x1, img_w))
            x2 = max(0, min(x2, img_w))
        if img_h is not None:
            y1 = max(0, min(y1, img_h))
            y2 = max(0, min(y2, img_h))
        
        # ensure positive area
        w = x2 - x1
        h = y2 - y1
        if w <= 0 or h <= 0:
            continue
        
        # enforce minimum size
        if w <= width_tolerance or h <= height_tolerance:
            continue
        
        cleaned.append([x1, y1, x2, y2])

    return np.array(cleaned, dtype=int)


def get_inpaint_mask(
    text_bbox: list[float],
    image: np.ndarray,
) -> np.ndarray:
    """
    Get a pixel-accurate inpaint mask for a text region in full-image coordinates.
    """
    if image is None or image.size == 0:
        return np.zeros(image.shape[:2], dtype=np.uint8) if image is not None else np.zeros((0, 0), dtype=np.uint8)

    x1, y1, x2, y2 = adjust_text_line_coordinates(text_bbox, 10, 10, image)
    crop = image[y1:y2, x1:x2]
    crop_mask = detect_content_mask_in_bbox(crop)
    full_mask = np.zeros(image.shape[:2], dtype=np.uint8)
    if crop_mask.size > 0:
        full_mask[y1:y2, x1:x2] = crop_mask
    return full_mask


def _process_stats_vectorized(
    stats: np.ndarray, 
    image_shape: tuple[int, int], 
    min_area: int, 
    margin: int = 0,
    small_component_min_area: int = 4,
    small_component_max_span: int = 6,
) -> np.ndarray:
    """
    Helper to filter stats using NumPy vectorization, with a border margin.
    
    Args:
        stats (np.ndarray): The stats array from connectedComponentsWithStats.
        image_shape (tuple): The (height, width) of the image.
        min_area (int): Minimum area for a component to be considered.
        margin (int): The number of pixels to exclude from each border.
                      Components touching this margin will be removed.
    """
    # The stats array includes the background at index 0. We slice from [1:] to exclude it.
    stats_no_bg = stats[1:]
    
    if stats_no_bg.shape[0] == 0:
        return np.empty((0, 4), dtype=int)
    
    height, width = image_shape

    # 1. Create a boolean mask for all conditions
    
    # Condition 1: Area is greater than min_area.
    x1 = stats_no_bg[:, imk.CC_STAT_LEFT]
    y1 = stats_no_bg[:, imk.CC_STAT_TOP]
    w = stats_no_bg[:, imk.CC_STAT_WIDTH]
    h = stats_no_bg[:, imk.CC_STAT_HEIGHT]
    area = stats_no_bg[:, imk.CC_STAT_AREA]
    area_mask = area > min_area

    # Keep punctuation-sized components even when their filled area is tiny.
    small_component_mask = (
        (area >= small_component_min_area)
        & (w <= small_component_max_span)
        & (h <= small_component_max_span)
    )

    # Condition 2: Bounding box is NOT within the margin of the border.

    border_mask = (x1 >= margin) & \
                  (y1 >= margin) & \
                  ((x1 + w) <= width - margin) & \
                  ((y1 + h) <= height - margin)
    
    # Combine all masks
    final_mask = (area_mask | small_component_mask) & border_mask
    
    # Apply the mask to get only the valid components
    valid_stats = stats_no_bg[final_mask]
    
    if valid_stats.shape[0] == 0:
        return np.empty((0, 4), dtype=int)

    # Convert the filtered stats to [x1, y1, x2, y2] format in one go
    x1_f = valid_stats[:, imk.CC_STAT_LEFT]
    y1_f = valid_stats[:, imk.CC_STAT_TOP]
    x2_f = x1_f + valid_stats[:, imk.CC_STAT_WIDTH]
    y2_f = y1_f + valid_stats[:, imk.CC_STAT_HEIGHT]

    content_bboxes = np.stack([x1_f, y1_f, x2_f, y2_f], axis=1) 

    return content_bboxes.astype(int)


def detect_content_in_bbox(
    image: np.ndarray, 
    min_area: int = 10, 
    margin: int = 1
) -> np.ndarray:
    """
    Detects content using mahotas stats and fast NumPy vectorized filtering.

    Args:
        image (np.ndarray): Input cropped image.
        min_area (int): Minimum area of detected text box.
        margin (int): The number of pixels to exclude from each border.

    Returns:
        np.ndarray: Bounding boxes of shape (N, 4) in [x1, y1, x2, y2] format.
    """
    if image is None or image.size == 0:
        return np.empty((0, 4), dtype=int)

    gray = imk.to_gray(image)
    threshold = mahotas.thresholding.otsu(gray)
    
    binary_black_text = (gray < threshold).astype(np.uint8)
    binary_white_text = (gray > threshold).astype(np.uint8)
    if not np.any(binary_black_text):
        binary_black_text = (gray == gray.min()).astype(np.uint8)
    if not np.any(binary_white_text):
        binary_white_text = (gray == gray.max()).astype(np.uint8)
    
    # Convert boolean to uint8 for connectedComponentsWithStats
    _, _, stats_white, _ = imk.connected_components_with_stats(binary_white_text, connectivity=8)
    _, _, stats_black, _ = imk.connected_components_with_stats(binary_black_text, connectivity=8)

    image_shape = image.shape[:2]

    # Pass the new margin parameter to the helper function
    bboxes_white = _process_stats_vectorized(stats_white, image_shape, min_area, margin)
    bboxes_black = _process_stats_vectorized(stats_black, image_shape, min_area, margin)
    
    # Combine the results
    if bboxes_white.shape[0] > 0 and bboxes_black.shape[0] > 0:
        return np.vstack([bboxes_white, bboxes_black])
    elif bboxes_white.shape[0] > 0:
        return bboxes_white
    else:
        return bboxes_black


def detect_content_mask_in_bbox(
    image: np.ndarray,
    min_area: int = 10,
    margin: int = 1,
) -> np.ndarray:
    """
    Detect text-like content as a binary component mask instead of box unions.
    """
    if image is None or image.size == 0:
        return np.zeros((0, 0), dtype=np.uint8)

    gray = imk.to_gray(image)
    threshold = mahotas.thresholding.otsu(gray)

    binary_black_text = (gray < threshold).astype(np.uint8)
    binary_white_text = (gray > threshold).astype(np.uint8)
    if not np.any(binary_black_text):
        binary_black_text = (gray == gray.min()).astype(np.uint8)
    if not np.any(binary_white_text):
        binary_white_text = (gray == gray.max()).astype(np.uint8)

    mask_black = _mask_from_component_stats(binary_black_text, min_area=min_area, margin=margin)
    mask_white = _mask_from_component_stats(binary_white_text, min_area=min_area, margin=margin)
    return np.where((mask_black > 0) | (mask_white > 0), 255, 0).astype(np.uint8)


def _mask_from_component_stats(
    binary_mask: np.ndarray,
    *,
    min_area: int,
    margin: int,
    small_component_min_area: int = 4,
    small_component_max_span: int = 6,
) -> np.ndarray:
    num_labels, labels, stats, _ = imk.connected_components_with_stats(binary_mask, connectivity=8)
    if num_labels <= 1:
        return np.zeros(binary_mask.shape[:2], dtype=np.uint8)

    stats_no_bg = stats[1:]
    if stats_no_bg.shape[0] == 0:
        return np.zeros(binary_mask.shape[:2], dtype=np.uint8)

    height, width = binary_mask.shape[:2]
    x1 = stats_no_bg[:, imk.CC_STAT_LEFT]
    y1 = stats_no_bg[:, imk.CC_STAT_TOP]
    w = stats_no_bg[:, imk.CC_STAT_WIDTH]
    h = stats_no_bg[:, imk.CC_STAT_HEIGHT]
    area = stats_no_bg[:, imk.CC_STAT_AREA]

    area_mask = area > min_area
    small_component_mask = (
        (area >= small_component_min_area)
        & (w <= small_component_max_span)
        & (h <= small_component_max_span)
    )
    border_mask = (
        (x1 >= margin)
        & (y1 >= margin)
        & ((x1 + w) <= width - margin)
        & ((y1 + h) <= height - margin)
    )
    keep = (area_mask | small_component_mask) & border_mask
    if not np.any(keep):
        return np.zeros(binary_mask.shape[:2], dtype=np.uint8)

    keep_labels = np.flatnonzero(keep) + 1
    return np.where(np.isin(labels, keep_labels), 255, 0).astype(np.uint8)
