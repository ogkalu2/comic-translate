from typing import List, Tuple
import numpy as np
import cv2

class TextBlock(object):
    """
    Object that stores a block of text. Optionally stores the list of lines
    """
    def __init__(self, 
                 text_bbox: np.ndarray = None,
                 bubble_bbox: np.ndarray = None,
                 text_class: str = "",
                 inpaint_bboxes = None,
                 lines: List = None,
                 text_segm_points: np.ndarray = None, 
                 angle = 0,
                 text: str = "",
                 texts: List[str] = None,
                 translation: str = "",
                 line_spacing = 1,
                 alignment: str = '',
                 source_lang: str = "",
                 target_lang: str = "",
                 min_font_size: int = 0,
                 max_font_size: int = 0,
                 font_color: str = "",
                 **kwargs) -> None:
        
        self.xyxy = text_bbox
        self.segm_pts = text_segm_points
        self.bubble_xyxy = bubble_bbox
        self.text_class = text_class
        self.angle = angle
        self.tr_origin_point = ()
 
        self.lines = lines
        if isinstance(inpaint_bboxes, np.ndarray):
            self.inpaint_bboxes = inpaint_bboxes
        else:
            self.inpaint_bboxes = np.array(inpaint_bboxes, dtype=np.int32) if inpaint_bboxes else None
        self.texts = texts if texts is not None else []
        self.text = ' '.join(self.texts) if self.texts else text
        self.translation = translation

        self.line_spacing = line_spacing
        self.alignment = alignment
        
        self.source_lang = source_lang
        self.target_lang = target_lang

        self.min_font_size = min_font_size
        self.max_font_size = max_font_size
        self.font_color = font_color

    @property
    def xywh(self):
        x1, y1, x2, y2 = self.xyxy
        return np.array([x1, y1, x2-x1, y2-y1]).astype(np.int32)

    @property
    def center(self) -> np.ndarray:
        xyxy = np.array(self.xyxy)
        return (xyxy[:2] + xyxy[2:]) / 2
    
    @property
    def source_lang_direction(self):
        if self.source_lang == 'ja':
            return 'ver_rtl'
        else:
            return 'hor_ltr'

def sort_blk_list(blk_list: List[TextBlock], right_to_left=True) -> List[TextBlock]:
    # Sort blk_list from right to left, top to bottom
    sorted_blk_list = []
    for blk in sorted(blk_list, key=lambda blk: blk.center[1]):
        for i, sorted_blk in enumerate(sorted_blk_list):
            if blk.center[1] > sorted_blk.xyxy[3]:
                continue
            if blk.center[1] < sorted_blk.xyxy[1]:
                sorted_blk_list.insert(i + 1, blk)
                break

            # y center of blk inside sorted_blk so sort by x instead
            if right_to_left and blk.center[0] > sorted_blk.center[0]:
                sorted_blk_list.insert(i, blk)
                break
            if not right_to_left and blk.center[0] < sorted_blk.center[0]:
                sorted_blk_list.insert(i, blk)
                break
        else:
            sorted_blk_list.append(blk)
    return sorted_blk_list

def sort_textblock_rectangles(coords_text_list: List[Tuple[Tuple[int, int, int, int], str]], direction: str = 'ver_rtl', threshold: int = 10):
    
    def in_same_line(bbox_a, bbox_b, direction, threshold):
        """
        Checks if two bounding boxes are on the same line based on their relative positions.

        Args:
            bbox_a (tuple): Bounding box coordinates for the first object (x1, y1, x2, y2).
            bbox_b (tuple): Bounding box coordinates for the second object (x1, y1, x2, y2).
            direction (str): The predominant text direction, either 'horizontal' or 'vertical'.
            threshold (float): Maximum distance between the centers of the bounding boxes to be considered on the same line.

        Returns:
            bool: True if the bounding boxes are on the same line, False otherwise.
        """
        # Calculate the center points of the bounding boxes
        center_a = ((bbox_a[0] + bbox_a[2]) / 2, (bbox_a[1] + bbox_a[3]) / 2)
        center_b = ((bbox_b[0] + bbox_b[2]) / 2, (bbox_b[1] + bbox_b[3]) / 2)

        # For horizontal text, check if the centers are within the same horizontal band
        if 'hor' in direction:
            return abs(center_a[1] - center_b[1]) <= threshold
        # For vertical text, check if the centers are within the same vertical band
        elif 'ver' in direction:
            return abs(center_a[0] - center_b[0]) <= threshold

    # Group word bounding boxes into lines
    lines = []
    remaining_boxes = coords_text_list[:]  # create a shallow copy

    while remaining_boxes:
        box = remaining_boxes.pop(0)
        current_line = [box]
        closest_line = None
        closest_distance = float('inf')

        # Find the closest existing line to the current bounding box
        for line in lines:
            for line_box in line:
                if in_same_line(box[0], line_box[0], direction, threshold):
                    distance = abs(box[0][0] - line_box[0][0]) + abs(box[0][1] - line_box[0][1])
                    if distance < closest_distance:
                        closest_line = line
                        closest_distance = distance

        # If a close line was found, add the bounding box to that line
        if closest_line is not None:
            closest_line.append(box)
        # Otherwise, create a new line with the current bounding box
        else:
            lines.append(current_line)

    # Sort the boxes in each line based on the reading direction
    for i, line in enumerate(lines):
        if direction == 'hor_ltr':
            lines[i] = sorted(line, key=lambda box: box[0][0])  # Sort by leftmost x-coordinate
        elif direction == 'hor_rtl':
            lines[i] = sorted(line, key=lambda box: -box[0][0])  # Sort by leftmost x-coordinate, reversed
        elif direction in ['ver_ltr', 'ver_rtl']:
            lines[i] = sorted(line, key=lambda box: box[0][1])  # Sort by topmost y-coordinate

    # Sort the lines themselves based on the orientation of the text
    if 'hor' in direction:
        lines.sort(key=lambda line: min(box[0][1] for box in line))  # Sort by topmost y-coordinate for horizontal text
    elif direction == 'ver_ltr':
        lines.sort(key=lambda line: min(box[0][0] for box in line)) # Sort by leftmost x-coordinate for vertical text
    elif direction == 'ver_rtl':
        lines.sort(key=lambda line: min(box[0][0] for box in line), reverse=True)  # Reversed order of sort by leftmost x-coordinate 

    # Flatten the list of lines to return a single list with all grouped boxes
    grouped_boxes = [box for line in lines for box in line]
    
    return grouped_boxes

def visualize_textblocks(canvas, blk_list: List[TextBlock]):
    lw = max(round(sum(canvas.shape) / 2 * 0.003), 2)  # line width
    for i, blk in enumerate(blk_list):
        bx1, by1, bx2, by2 = blk.xyxy
        cv2.rectangle(canvas, (bx1, by1), (bx2, by2), (127, 255, 127), lw)
        for j, line in enumerate(blk.lines):
            cv2.putText(canvas, str(j), line[0], cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255,127,0), 1)
            cv2.polylines(canvas, [line], True, (0,127,255), 2)
        # cv2.polylines(canvas, [blk.min_rect], True, (127,127,0), 2)
        cv2.putText(canvas, str(i), (bx1, by1 + lw), 0, lw / 3, (255,127,127), max(lw-1, 1), cv2.LINE_AA)
        #center = [int((bx1 + bx2)/2), int((by1 + by2)/2)]
        # cv2.putText(canvas, 'a: %.2f' % blk.angle, [bx1, center[1]], cv2.FONT_HERSHEY_SIMPLEX, 1, (127,127,255), 2)
        #cv2.putText(canvas, 'x: %s' % bx1, [bx1, center[1] + 30], cv2.FONT_HERSHEY_SIMPLEX, 1, (127,127,255), 2)
        #cv2.putText(canvas, 'y: %s' % by1, [bx1, center[1] + 60], cv2.FONT_HERSHEY_SIMPLEX, 1, (127,127,255), 2)
    return canvas

def visualize_speech_bubbles(canvas, blk_list: List[TextBlock]):
    lw = max(round(sum(canvas.shape) / 2 * 0.003), 2)  # line width

    # Define a color for each class
    class_colors = {
        'text_free': (255, 0, 0),   # Blue color for class_name_1
        'text_bubble': (0, 255, 0),   # Green color for class_name_2
    }

    for blk in blk_list:
        bx1, by1, bx2, by2 = blk.bubble_xyxy

        # Select the color for the current class
        color = class_colors.get(blk.text_class, (127, 255, 127))  # Default color if class not found

        # Draw the bounding box with the selected color
        cv2.rectangle(canvas, (bx1, by1), (bx2, by2), color, lw)

        #label = f"{conf * 100:.2f}%"  # e.g., '0: text_bubble 95.43%'
        #(text_width, text_height), baseline = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, lw / 6, max(lw - 1, 1))
        # Draw the label
        #cv2.rectangle(canvas, (bx1, by1 - text_height - baseline - 3), (bx1 + text_width, by1), color, -1)
        #cv2.putText(canvas, label, (bx1, by1 - baseline), cv2.FONT_HERSHEY_SIMPLEX, lw / 6, (255, 255, 255), max(lw - 1, 1), cv2.LINE_AA)

    return canvas

def adjust_text_line_coordinates(coords, width_expansion_percentage: int, height_expansion_percentage: int, img: np.ndarray):
    top_left_x, top_left_y, bottom_right_x, bottom_right_y = coords
    im_h, im_w, _ = img.shape
    
    # Calculate width, height, and respective expansion offsets
    width = bottom_right_x - top_left_x
    height = bottom_right_y - top_left_y
    width_expansion_offset = int(((width * width_expansion_percentage) / 100) / 2)
    height_expansion_offset = int(((height * height_expansion_percentage) / 100) / 2)

    # Define the rectangle origin points (bottom left, top right) with expansion/contraction
    new_x1 = max(top_left_x - width_expansion_offset, 0)
    new_y1 = max(top_left_y - height_expansion_offset, 0)
    new_x2 = min(bottom_right_x + width_expansion_offset, im_w)
    new_y2 = min(bottom_right_y + height_expansion_offset, im_h)

    return new_x1, new_y1, new_x2, new_y2

def adjust_blks_size(blk_list: List[TextBlock], img: np.ndarray, w_expan: int = 0, h_expan: int = 0):
    for blk in blk_list:
        coords = blk.xyxy
        expanded_coords = adjust_text_line_coordinates(coords, w_expan, h_expan, img)
        blk.xyxy[:] = expanded_coords

