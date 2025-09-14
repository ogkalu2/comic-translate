"""
Geometric operations and calculations for detection.
"""
import numpy as np
from typing import Sequence

RectLike = Sequence[int]  # expects length 4: (x1,y1,x2,y2)
BBox = tuple[int, int, int, int]


def calculate_iou(rect1: list[float], rect2: list[float]) -> float:
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


def do_rectangles_overlap(
    rect1: list[float], 
    rect2: list[float], 
    iou_threshold: float = 0.2
) -> bool:
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


def does_rectangle_fit(bigger_rect: list[float], smaller_rect: list[float]) -> bool:
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


def is_mostly_contained(
    outer_box: list[float], 
    inner_box: list[float], 
    threshold: float
) -> bool:
    """
    Check if inner_box is mostly contained within outer_box.
    
    Args:
        outer_box: The larger bounding box (x1, y1, x2, y2)
        inner_box: The smaller bounding box (x1, y1, x2, y2)
        threshold: The proportion of inner_box that must be inside outer_box
    
    Returns:
        Boolean indicating if inner_box is mostly contained in outer_box
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


def merge_boxes(box1: list[float], box2: list[float]) -> list[float]:
    """
    Merge two bounding boxes.
    
    Args:
        box1: First bounding box [x1, y1, x2, y2]
        box2: Second bounding box [x1, y1, x2, y2]
    
    Returns:
        Merged bounding box [x1, y1, x2, y2]
    """
    return [
        min(box1[0], box2[0]),
        min(box1[1], box2[1]),
        max(box1[2], box2[2]),
        max(box1[3], box2[3])
    ]


def merge_overlapping_boxes(
    bboxes: np.ndarray,
    containment_threshold: float = 0.3,
    overlap_threshold: float = 0.5,
) -> np.ndarray:
    """
    Merge boxes that are mostly contained within each other, and
    prune out duplicates/overlaps immediately as you go.
    
    Args:
        bboxes: Array of bounding boxes
        containment_threshold: Threshold for containment-based merging
        overlap_threshold: Threshold for overlap-based filtering
    
    Returns:
        Array of merged and filtered bounding boxes
    """
    accepted = []

    for i, box in enumerate(bboxes):
        # 1) Merge this box against all others based on containment:
        merged = box.copy()
        for j, other in enumerate(bboxes):
            if i == j:
                continue
            if (is_mostly_contained(merged, other, containment_threshold)
             or is_mostly_contained(other, merged, containment_threshold)):
                merged = merge_boxes(merged, other)

        # 2) On-the-fly pruning: see if `merged` overlaps or duplicates any accepted box
        conflict = False
        for acc in accepted:
            if np.array_equal(merged, acc) or do_rectangles_overlap(merged, acc, overlap_threshold):
                conflict = True
                break

        if conflict:
            # skip this one entirely
            continue

        # 3) Optionally, remove any already-accepted boxes that overlap too much with the new merged box
        accepted = [
            acc for acc in accepted
            if not (np.array_equal(acc, merged)
                    or do_rectangles_overlap(merged, acc, overlap_threshold))
        ]

        # 4) Finally accept the new box
        accepted.append(merged)

    return np.array(accepted)


def calculate_polygon_angle(polygon_points: list[list[float]]) -> float:
    """
    Calculate the angle of a polygon by finding the dominant edge direction.
    
    Args:
        polygon_points: Array of points defining the polygon [(x1,y1), (x2,y2), ...]
    
    Returns:
        Angle in degrees (0-360)
    """
    if len(polygon_points) < 4:
        return 0
    
    # Convert to numpy array if not already
    points = np.array(polygon_points)
    
    # Calculate the primary direction using the top and bottom edges
    # Assume points are ordered: top-left, top-right, bottom-right, bottom-left
    if len(points) >= 4:
        # Top edge vector
        top_vector = points[1] - points[0]
        # Bottom edge vector  
        bottom_vector = points[2] - points[3]
        
        # Average the vectors to get dominant direction
        avg_vector = (top_vector + bottom_vector) / 2
        
        # Calculate angle in degrees
        angle = np.degrees(np.arctan2(avg_vector[1], avg_vector[0]))
        
        # Normalize to 0-360 range
        if angle < 0:
            angle += 360
            
        return angle
    
    return 0


def find_polygons_in_textblock(
    text_bbox: list[float], 
    detection_polygons: list[list[list[float]]], 
    containment_threshold: float = 0.7
) -> list[list[list[float]]]:
    """
    Find detection polygons that belong to a specific text block.
    
    Args:
        text_bbox: Text block bounding box [x1, y1, x2, y2]
        detection_polygons: list of polygon coordinates from detection results
        containment_threshold: Minimum overlap ratio to consider a polygon as belonging to the text block
    
    Returns:
        list of polygons that belong to this text block
    """
    matching_polygons = []
    
    if not detection_polygons:
        return matching_polygons
    
    text_x1, text_y1, text_x2, text_y2 = text_bbox
    text_area = (text_x2 - text_x1) * (text_y2 - text_y1)
    
    for polygon in detection_polygons:
        if len(polygon) < 4:
            continue
            
        # Convert polygon to bounding box for easier calculation
        poly_points = np.array(polygon)
        poly_x1, poly_y1 = poly_points[:, 0].min(), poly_points[:, 1].min()
        poly_x2, poly_y2 = poly_points[:, 0].max(), poly_points[:, 1].max()
        poly_area = (poly_x2 - poly_x1) * (poly_y2 - poly_y1)
        
        # Calculate intersection
        intersect_x1 = max(text_x1, poly_x1)
        intersect_y1 = max(text_y1, poly_y1)
        intersect_x2 = min(text_x2, poly_x2)
        intersect_y2 = min(text_y2, poly_y2)
        
        if intersect_x2 > intersect_x1 and intersect_y2 > intersect_y1:
            intersect_area = (intersect_x2 - intersect_x1) * (intersect_y2 - intersect_y1)
            
            # Check if polygon is mostly contained in text block
            polygon_containment = intersect_area / poly_area if poly_area > 0 else 0
            
            if polygon_containment >= containment_threshold:
                matching_polygons.append(polygon)
            # Also check if text block mostly fits in polygon (for cases where detection is larger)
            elif intersect_area / text_area >= containment_threshold:
                matching_polygons.append(polygon)
    
    return matching_polygons


def shrink_bbox(
    bubble_bbox: BBox, 
    shrink_percent: float = 0.15
) -> BBox:
    """
    Finds an interior bounding box by shrinking the given bounding box.
    
    Args:
        bubble_bbox: The bubble bounding box (x1, y1, x2, y2)
        shrink_percent: The percentage to shrink the bounding box by on each side.
    
    Returns:
        A tuple (x1, y1, x2, y2) for the interior bounds.
    """
    x1, y1, x2, y2 = bubble_bbox
    
    width = x2 - x1
    height = y2 - y1
    
    # Shrink the box to get an "interior" rectangle
    dx = int(width * shrink_percent)
    dy = int(height * shrink_percent)
    
    ix1, iy1 = x1 + dx, y1 + dy
    ix2, iy2 = x2 - dx, y2 - dy
    
    # Ensure the shrunk box still has a positive area
    if ix2 <= ix1 or iy2 <= iy1:
        return x1, y1, x2, y2
    
    return ix1, iy1, ix2, iy2
