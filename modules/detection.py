from ultralytics import YOLO
import largestinteriorrectangle as lir
from .utils.textblock import TextBlock, adjust_text_line_coordinates
import numpy as np 
import cv2


class TextBlockDetector:
    def __init__(self, bubble_model_path: str, text_seg_model_path: str, text_detect_model_path: str, device: str):
        self.bubble_detection = YOLO(bubble_model_path)
        self.text_segmentation = YOLO(text_seg_model_path)
        self.text_detection = YOLO(text_detect_model_path)
        self.device = device

    def detect(self, img):
        self.image = img

        h, w, _ = img.shape
        size = (h, w) if h >= w * 5 else 1024
        det_size = (h, w) if h >= w * 5 else 640

        bble_detec_result = self.bubble_detection(img, device=self.device, imgsz=size, conf=0.1, verbose=False)[0]
        txt_seg_result = self.text_segmentation(img, device=self.device, imgsz=size, conf=0.1, verbose=False)[0]
        txt_detect_result = self.text_detection(img, device=self.device, imgsz=det_size, conf=0.2, verbose=False)[0]

        combined = self.combine_results(bble_detec_result, txt_seg_result, txt_detect_result)

        blk_list = [TextBlock(txt_bbox, bble_bbox, txt_class, inp_bboxes)
                for txt_bbox, bble_bbox, inp_bboxes, txt_class in combined]
        
        return blk_list
    
    def combine_results(self, bubble_detec_results: YOLO, text_seg_results: YOLO, text_detect_results: YOLO):
        bubble_bounding_boxes = np.array(bubble_detec_results.boxes.xyxy.cpu(), dtype="int")
        
        seg_text_bounding_boxes = np.array(text_seg_results.boxes.xyxy.cpu(), dtype="int")
        detect_text_bounding_boxes = np.array(text_detect_results.boxes.xyxy.cpu(), dtype="int")

        text_bounding_boxes = merge_bounding_boxes(seg_text_bounding_boxes, detect_text_bounding_boxes)

        text_blocks_bboxes = []
        # Process each text bounding box
        for bbox in text_bounding_boxes:
            adjusted_bboxes = get_inpaint_bboxes(bbox, self.image)
            text_blocks_bboxes.append(adjusted_bboxes)

        raw_results = []
        text_matched = [False] * len(text_bounding_boxes)

        if text_bounding_boxes is not None or len(text_bounding_boxes) > 0:
            for txt_idx, txt_box in enumerate(text_bounding_boxes):
                for bble_box in bubble_bounding_boxes:

                    if does_rectangle_fit(bble_box, txt_box):
                        raw_results.append((txt_box, bble_box, text_blocks_bboxes[txt_idx], 'text_bubble'))
                        text_matched[txt_idx] = True
                        break
                    elif do_rectangles_overlap(bble_box, txt_box):
                        raw_results.append((txt_box, bble_box, text_blocks_bboxes[txt_idx], 'text_free'))
                        text_matched[txt_idx] = True
                        break

                if not text_matched[txt_idx]:
                    raw_results.append((txt_box, None, text_blocks_bboxes[txt_idx], 'text_free'))

        return raw_results
    
def get_inpaint_bboxes(text_bbox, image):
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

def calculate_iou(rect1, rect2) -> float:
    """
    Calculate the Intersection over Union (IoU) of two rectangles.
    
    Parameters:
    rect1, rect2: The coordinates of the rectangles in the format
    [x1, y1, x2, y2], where (x1, y1) is the top-left coordinate and (x2, y2) is the bottom-right coordinate.
    
    Returns:
    iou: the Intersection over Union (IoU) metric as a float.
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
    Determines whether two rectangles refer to the same object based on an IoU threshold.
    
    Parameters:
    rect1, rect2: as described in the calculate_iou function.
    iou_threshold: float value representing the threshold above which the rectangles are
    considered to be referring to the same object.
    
    Returns:
    overlap: a boolean indicating whether the two rectangles refer to the same object.
    """
    iou = calculate_iou(rect1, rect2)
    overlap = iou >= iou_threshold
    return overlap

def does_rectangle_fit(bigger_rect, smaller_rect):
    x1, y1, x2, y2 = bigger_rect
    px1, py1, px2, py2 = smaller_rect
    
    # Ensure the coordinates are properly ordered
    # first rectangle
    left1, top1, right1, bottom1 = min(x1, x2), min(y1, y2), max(x1, x2), max(y1, y2)
    # second rectangle
    left2, top2, right2, bottom2 = min(px1, px2), min(py1, py2), max(px1, px2), max(py1, py2)
    
    # Check if the second rectangle fits within the first
    fits_horizontally = left1 <= left2 and right1 >= right2
    fits_vertically = top1 <= top2 and bottom1 >= bottom2
    
    return fits_horizontally and fits_vertically

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
    if outer_area < inner_area:
        return False
    
    # Calculate the area of intersection
    intersection_area = max(0, min(ix2, ox2) - max(ix1, ox1)) * max(0, min(iy2, oy2) - max(iy1, oy1))
    
    # Check if the proportion of intersection to inner area is greater than the threshold
    return intersection_area / inner_area >= threshold

def merge_boxes(box1, box2):
    """Merge two bounding boxes"""
    return [
        min(box1[0], box2[0]),
        min(box1[1], box2[1]),
        max(box1[2], box2[2]),
        max(box1[3], box2[3])
    ]

def merge_bounding_boxes(seg_boxes, detect_boxes):
    merged_boxes = []

    # First step: Merge seg_boxes with detect_boxes
    # When the text has no bubbles, The Segmentatio Model tends to predict large boxes that aim to cover most of the text,
    # but the detection model tends to predict each line as a separate box
    for seg_box in seg_boxes:
        running_box = seg_box
        for detect_box in detect_boxes:
            if does_rectangle_fit(running_box, detect_box):
                continue  # Detect box fits entirely within the running box
            if do_rectangles_overlap(running_box, detect_box, 0.02):
                # Merge running_box with the detect_box and update the running_box
                running_box = merge_boxes(running_box, detect_box)
        
        merged_boxes.append(running_box)  # Add the final running box for this seg box

    # Now add any detect boxes that weren't merged
    for detect_box in detect_boxes:
        add_box = True
        for merged_box in merged_boxes:
            if do_rectangles_overlap(detect_box, merged_box, 0.1) or does_rectangle_fit(merged_box, detect_box):
                add_box = False
                break
        if add_box:
            merged_boxes.append(detect_box)

    # Second step: Re-process merged_boxes to handle overlaps that should be merged into a bigger box
    final_boxes = []
    for i, box in enumerate(merged_boxes):
        running_box = box
        for j, other_box in enumerate(merged_boxes):
            if i == j:
                continue  # Skip comparing the box with itself
            if do_rectangles_overlap(running_box, other_box, 0.1) and not does_rectangle_fit(running_box, other_box):
                # Re-merge running_box with the overlapping other_box
                running_box = merge_boxes(running_box, other_box)
        
        final_boxes.append(running_box)  # Add the final running box after second pass

    # Remove duplicates and high-overlap boxes
    unique_boxes = []
    seen_boxes = []
    for box in final_boxes:
        duplicate = False
        for seen_box in seen_boxes:
            if (np.array_equal(box, seen_box) or do_rectangles_overlap(box, seen_box, 0.6)):
                duplicate = True
                break
        if not duplicate:
            unique_boxes.append(box)
            seen_boxes.append(box)  # Track the box that we've added to the final list

    return np.array(unique_boxes)


def detect_content_in_bbox(image):
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


# From https://github.com/TareHimself/manga-translator/blob/master/translator/utils.py

def adjust_contrast_brightness(img: np.ndarray, contrast: float = 1.0, brightness: int = 0):
    """
    Adjusts contrast and brightness of an uint8 image.
    contrast:   (0.0,  inf) with 1.0 leaving the contrast as is
    brightness: [-255, 255] with 0 leaving the brightness as is
    """
    brightness += int(round(255 * (1 - contrast) / 2))
    return cv2.addWeighted(img, contrast, img, 0, brightness)

def ensure_gray(img: np.ndarray):
    if len(img.shape) > 2:
        return cv2.cvtColor(img.copy(), cv2.COLOR_BGR2GRAY)
    return img.copy()

def make_bubble_mask(frame: np.ndarray):
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
    gray = ensure_gray(frame_mask)
    # Threshold the image
    ret, thresh = cv2.threshold(gray, 200, 255, 0)
    
    # Find contours
    contours, hierarchy = cv2.findContours(thresh, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_NONE)
    largest_contour = max(contours, key=cv2.contourArea) 
    return largest_contour

def bubble_interior_bounds(frame_mask: np.ndarray):
    bble_contour = bubble_contour(frame_mask)

    polygon = np.array([bble_contour[:, 0, :]])
    rect = lir.lir(polygon)

    x1, y1 = lir.pt1(rect)
    x2, y2 = lir.pt2(rect)

    return x1, y1, x2, y2

