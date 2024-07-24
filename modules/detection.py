from ultralytics import YOLO
import largestinteriorrectangle as lir
from .utils.textblock import TextBlock
import numpy as np 
import cv2


class TextBlockDetector:
    def __init__(self, bubble_model_path: str, text_model_path: str, device: str):
        self.bubble_detection = YOLO(bubble_model_path)
        self.text_segmentation = YOLO(text_model_path)
        self.device = device

    def detect(self, img):

        h, w, _ = img.shape
        size = (h, w) if h >= w * 5 else 1024

        bble_detec_result = self.bubble_detection(img, device=self.device, imgsz=size, conf=0.1, verbose=False)[0]
        txt_seg_result = self.text_segmentation(img, device=self.device, imgsz=size, conf=0.1, verbose=False)[0]

        combined = combine_results(bble_detec_result, txt_seg_result)

        blk_list = [TextBlock(txt_bbox, txt_seg_points, bble_bbox, txt_class)
                for txt_bbox, bble_bbox, txt_seg_points, txt_class in combined]
        
        return blk_list

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

def combine_results(bubble_detec_results: YOLO, text_seg_results: YOLO):
    bubble_bounding_boxes = np.array(bubble_detec_results.boxes.xyxy.cpu(), dtype="int")
    text_bounding_boxes = np.array(text_seg_results.boxes.xyxy.cpu(), dtype="int")

    segment_points = []
    if text_seg_results.masks is not None:
        segment_points = list(map(lambda a: a.astype("int"), text_seg_results.masks.xy))

    raw_results = []
    text_matched = [False] * len(text_bounding_boxes)
    
    if segment_points:
        for txt_idx, txt_box in enumerate(text_bounding_boxes):
            for bble_box in bubble_bounding_boxes:
                if does_rectangle_fit(bble_box, txt_box):
                    raw_results.append((txt_box, bble_box, segment_points[txt_idx], 'text_bubble'))
                    text_matched[txt_idx] = True
                    break
                elif do_rectangles_overlap(bble_box, txt_box):
                    raw_results.append((txt_box, bble_box, segment_points[txt_idx], 'text_free'))
                    text_matched[txt_idx] = True
                    break
        
        # if not text_matched[txt_idx]:
        #     raw_results.append((txt_box, None, segment_points[txt_idx], 'text_free'))

    return raw_results

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

def bubble_interior_bounds(frame_mask: np.ndarray):
    gray = ensure_gray(frame_mask)
    # Threshold the image
    ret, thresh = cv2.threshold(gray, 200, 255, 0)
    
    # Find contours
    contours, hierarchy = cv2.findContours(thresh, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_NONE)

    largest_contour = max(contours, key=cv2.contourArea)
    polygon = np.array([largest_contour[:, 0, :]])
    rect = lir.lir(polygon)

    x1, y1 = lir.pt1(rect)
    x2, y2 = lir.pt2(rect)

    return x1, y1, x2, y2

