"""
Utility functions for detection engines.
"""
import numpy as np
import cv2
import largestinteriorrectangle as lir
from modules.utils.textblock import adjust_text_line_coordinates


def calculate_iou(rect1, rect2) -> float:
    """
    Calculate the Intersection over Union (IoU) of two rectangles.
    
    Args:
        rect1: First rectangle as [x1, y1, x2, y2]
        rect2: Second rectangle as [x1, y1, x2, y2]
    
    Returns:
        IoU value as a float
    """
    x1 = max(rect1[0], rect2[0])
    y1 = max(rect1[1], rect2[1])
    x2 = min(rect1[2], rect2[2])
    y2 = min(rect1[3], rect2[3])
    
    intersection_area = max(0, x2 - x1) * max(0, y2 - y1)
    
    rect1_area = (rect1[2] - rect1[0]) * (rect1[3] - rect1[1])
    rect2_area = (rect2[2] - rect2[0]) * (rect2[3] - rect2[1])
    
    union_area = rect1_area + rect2_area - intersection_area
    
    iou = intersection_area / union_area if union_area != 0 else 0
    
    return iou


def do_rectangles_overlap(rect1, rect2, iou_threshold: float = 0.2) -> bool:
    """
    Check if two rectangles overlap based on IoU threshold.
    
    Args:
        rect1: First rectangle as [x1, y1, x2, y2]
        rect2: Second rectangle as [x1, y1, x2, y2]
        iou_threshold: Minimum IoU to consider as overlap
    
    Returns:
        True if rectangles overlap above threshold
    """
    iou = calculate_iou(rect1, rect2)
    return iou >= iou_threshold


def does_rectangle_fit(bigger_rect, smaller_rect) -> bool:
    """
    Check if smaller_rect fits entirely inside bigger_rect.
    
    Args:
        bigger_rect: Potential containing rectangle as [x1, y1, x2, y2]
        smaller_rect: Potential contained rectangle as [x1, y1, x2, y2]
    
    Returns:
        True if smaller_rect fits inside bigger_rect
    """
    x1, y1, x2, y2 = bigger_rect
    px1, py1, px2, py2 = smaller_rect
    
    # Ensure the coordinates are properly ordered
    left1, top1, right1, bottom1 = min(x1, x2), min(y1, y2), max(x1, x2), max(y1, y2)
    left2, top2, right2, bottom2 = min(px1, px2), min(py1, py2), max(px1, px2), max(py1, py2)
    
    # Check if the second rectangle fits within the first
    fits_horizontally = left1 <= left2 and right1 >= right2
    fits_vertically = top1 <= top2 and bottom1 >= bottom2
    
    return fits_horizontally and fits_vertically


def filter_bounding_boxes(bboxes, width_tolerance=5, height_tolerance=5):
    """
    Filter out bounding boxes that are too small in width or height.
    
    Args:
        bboxes: Array of bounding boxes as [x1, y1, x2, y2]
        width_tolerance: Minimum width to keep
        height_tolerance: Minimum height to keep
    
    Returns:
        Filtered array of bounding boxes
    """
    def is_close(value1, value2, tolerance):
        return abs(value1 - value2) <= tolerance

    if len(bboxes) == 0:
        return bboxes

    return np.array([
        bbox for bbox in bboxes
        if not (is_close(bbox[0], bbox[2], width_tolerance) or is_close(bbox[1], bbox[3], height_tolerance))
    ])


def detect_content_in_bbox(image):
    """
    Detect content (text) within a cropped image.
    
    Args:
        image: Cropped image containing text
    
    Returns:
        List of bounding boxes for detected content
    """
    if image is None or image.size == 0:
        return []
    
    # Convert to grayscale
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    
    # Adaptive Thresholding to handle varying illumination
    binary_white_text = cv2.adaptiveThreshold(
        gray, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY, 11, 2
    )
    binary_black_text = cv2.adaptiveThreshold(
        gray, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY_INV, 11, 2
    )
    
    # Perform connected component labeling for both cases
    num_labels_white, labels_white, stats_white, centroids_white = cv2.connectedComponentsWithStats(binary_white_text, connectivity=8)
    num_labels_black, labels_black, stats_black, centroids_black = cv2.connectedComponentsWithStats(binary_black_text, connectivity=8)
    
    # Filter out small components (likely to be noise)
    min_area = 10 
    content_bboxes = []
    
    height, width = image.shape[:2]
    
    # Process white text on black background
    for i in range(1, num_labels_white):  # Start from 1 to skip the background
        area = stats_white[i, cv2.CC_STAT_AREA]
        if area > min_area:
            x1 = stats_white[i, cv2.CC_STAT_LEFT]
            y1 = stats_white[i, cv2.CC_STAT_TOP]
            w = stats_white[i, cv2.CC_STAT_WIDTH]
            h = stats_white[i, cv2.CC_STAT_HEIGHT]
            x2 = x1 + w
            y2 = y1 + h
            
            # Check if the bounding box touches the edges of the image
            if x1 > 0 and y1 > 0 and x1 + w < width and y1 + h < height:
                content_bboxes.append((x1, y1, x2, y2))
    
    # Process black text on white background
    for i in range(1, num_labels_black):  # Start from 1 to skip the background
        area = stats_black[i, cv2.CC_STAT_AREA]
        if area > min_area:
            x1 = stats_black[i, cv2.CC_STAT_LEFT]
            y1 = stats_black[i, cv2.CC_STAT_TOP]
            w = stats_black[i, cv2.CC_STAT_WIDTH]
            h = stats_black[i, cv2.CC_STAT_HEIGHT]
            x2 = x1 + w
            y2 = y1 + h
            
            # Check if the bounding box touches the edges of the image
            if x1 > 0 and y1 > 0 and x1 + w < width and y1 + h < height:
                content_bboxes.append((x1, y1, x2, y2))
    
    return content_bboxes


def get_inpaint_bboxes(text_bbox, image):
    """
    Get inpaint bounding boxes for a text region.
    
    Args:
        text_bbox: Text bounding box [x1, y1, x2, y2]
        image: Full image
    
    Returns:
        List of inpaint bounding boxes
    """
    x1, y1, x2, y2 = adjust_text_line_coordinates(text_bbox, 0, 10, image)
        
    # Crop the image to the text bounding box
    crop = image[y1:y2, x1:x2]
        
    # Detect content in the cropped bubble
    content_bboxes = detect_content_in_bbox(crop)

    # Adjusting coordinates to the full image
    adjusted_bboxes = []
    for bbox in content_bboxes:
        lx1, ly1, lx2, ly2 = bbox
        adjusted_bbox = (x1 + lx1, y1 + ly1, x1 + lx2, y1 + ly2)
        adjusted_bboxes.append(adjusted_bbox)

    return adjusted_bboxes

def is_mostly_contained(outer_box, inner_box, threshold):
    """
    Check if inner_box is mostly contained within outer_box.
    
    :param outer_box: The larger bounding box (x1, y1, x2, y2)
    :param inner_box: The smaller bounding box (x1, y1, x2, y2)
    :param threshold: The proportion of inner_box that must be inside outer_box
    :return: Boolean indicating if inner_box is mostly contained in outer_box
    """
    ix1, iy1, ix2, iy2 = inner_box
    ox1, oy1, ox2, oy2 = outer_box
    
    # Calculate the area of the inner and outer boxes
    inner_area = (ix2 - ix1) * (iy2 - iy1)
    outer_area = (ox2 - ox1) * (oy2 - oy1)
    
    # Return False if the outer box is smaller than the inner box
    if outer_area < inner_area or inner_area == 0:
        return False
    
    # Calculate the area of intersection
    intersection_area = max(0, min(ix2, ox2) - max(ix1, ox1)) * max(0, min(iy2, oy2) - max(iy1, oy1))
    
    # Check if the proportion of intersection to inner area is greater than the threshold
    return intersection_area / inner_area >= threshold

# From https://github.com/TareHimself/manga-translator/blob/master/translator/utils.py

def adjust_contrast_brightness(img: np.ndarray, contrast: float = 1.0, brightness: int = 0):
    """
    Adjusts contrast and brightness of an uint8 image.
    
    Args:
        img: Input image
        contrast: Contrast adjustment factor
        brightness: Brightness adjustment value
    
    Returns:
        Adjusted image
    """
    brightness += int(round(255 * (1 - contrast) / 2))
    return cv2.addWeighted(img, contrast, img, 0, brightness)


def ensure_gray(img: np.ndarray):
    """
    Ensure image is grayscale.
    
    Args:
        img: Input image
    
    Returns:
        Grayscale image
    """
    if len(img.shape) > 2:
        return cv2.cvtColor(img.copy(), cv2.COLOR_BGR2GRAY)
    return img.copy()


def make_bubble_mask(frame: np.ndarray):
    """
    Create a mask for speech bubbles.
    
    Args:
        frame: Input image
    
    Returns:
        Bubble mask
    """
    image = frame.copy()
    # Apply a Gaussian blur to reduce noise
    blurred = cv2.GaussianBlur(image, (5, 5), 0)

    # Use the Canny edge detection algorithm
    edges = cv2.Canny(blurred, 50, 150)

    # Find contours in the image
    contours, _ = cv2.findContours(edges, cv2.RETR_TREE, cv2.CHAIN_APPROX_NONE)

    # Create a black image with the same size as the original
    stage_1 = cv2.drawContours(np.zeros_like(image), contours, -1, (255, 255, 255), thickness=2)
    stage_1 = cv2.bitwise_not(stage_1)
    stage_1 = cv2.cvtColor(stage_1, cv2.COLOR_BGR2GRAY)
    _, binary_image = cv2.threshold(stage_1, 200, 255, cv2.THRESH_BINARY)

    # Find connected components in the binary image
    num_labels, labels = cv2.connectedComponents(binary_image)
    largest_island_label = np.argmax(np.bincount(labels.flat)[1:]) + 1
    mask = np.zeros_like(image)
    mask[labels == largest_island_label] = 255

    _, mask = cv2.threshold(mask, 200, 255, cv2.THRESH_BINARY)

    # Apply morphological operations to remove black spots
    kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (3, 3))
    mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, kernel)

    return adjust_contrast_brightness(mask, 100)


def bubble_contour(frame_mask: np.ndarray):
    """
    Find the largest contour in a bubble mask.
    
    Args:
        frame_mask: Bubble mask
    
    Returns:
        Largest contour
    """
    gray = ensure_gray(frame_mask)
    # Threshold the image
    ret, thresh = cv2.threshold(gray, 200, 255, 0)
    
    # Find contours
    contours, hierarchy = cv2.findContours(thresh, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_NONE)
    largest_contour = max(contours, key=cv2.contourArea) 
    return largest_contour


def bubble_interior_bounds(frame_mask: np.ndarray):
    """
    Find interior bounds of a bubble.
    
    Args:
        frame_mask: Bubble mask
    
    Returns:
        Interior bounds as (x1, y1, x2, y2)
    """
    bble_contour = bubble_contour(frame_mask)

    polygon = np.array([bble_contour[:, 0, :]])
    rect = lir.lir(polygon)

    x1, y1 = lir.pt1(rect)
    x2, y2 = lir.pt2(rect)

    return x1, y1, x2, y2