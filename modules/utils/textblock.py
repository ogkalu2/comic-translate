from typing import List, Tuple
import numpy as np
import copy
from PIL import Image, ImageDraw
from collections import defaultdict, deque
from ..detection.utils.text_lines import group_items_into_lines
from modules.detection.utils.geometry import does_rectangle_fit, is_mostly_contained
from modules.utils.language_utils import is_no_space_lang

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
                 font_color: tuple = (),
                 direction: str = "",
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
        self.direction = direction

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
        if self.direction == 'vertical':
            return 'ver_rtl'
        else:
            return 'hor_ltr'
    
    def deep_copy(self):
        """
        Create a deep copy of this TextBlock instance.
        
        Returns:
            TextBlock: A new TextBlock instance with copied data
        """
        # Create a new TextBlock with copied numpy arrays and other data
        new_block = TextBlock()
        
        # Copy numpy arrays properly
        new_block.xyxy = self.xyxy.copy() if isinstance(self.xyxy, np.ndarray) else self.xyxy
        new_block.segm_pts = self.segm_pts.copy() if isinstance(self.segm_pts, np.ndarray) else self.segm_pts
        new_block.bubble_xyxy = self.bubble_xyxy.copy() if isinstance(self.bubble_xyxy, np.ndarray) else self.bubble_xyxy
        new_block.inpaint_bboxes = self.inpaint_bboxes.copy() if isinstance(self.inpaint_bboxes, np.ndarray) else self.inpaint_bboxes
        
        # Copy simple attributes
        new_block.text_class = self.text_class
        new_block.angle = self.angle
        new_block.tr_origin_point = copy.deepcopy(self.tr_origin_point)
        new_block.lines = copy.deepcopy(self.lines)
        new_block.texts = copy.deepcopy(self.texts)
        new_block.text = self.text
        new_block.translation = self.translation
        new_block.line_spacing = self.line_spacing
        new_block.alignment = self.alignment
        new_block.source_lang = self.source_lang
        new_block.target_lang = self.target_lang
        new_block.min_font_size = self.min_font_size
        new_block.max_font_size = self.max_font_size
        new_block.font_color = self.font_color
        
        return new_block

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

def sort_textblock_rectangles(
    coords_text_list: List[Tuple[Tuple[int, int, int, int], str]],
    direction: str = 'ver_rtl',
    band_ratio: float = 0.5,
) -> List[Tuple[Tuple[int, int, int, int], str]]:
    """
    Sort a list of (bbox, text) tuples into reading order using the
    shared grouping code in `group_items_into_lines`.

    This function now delegates line/column grouping to the detection
    utility which uses an adaptive band based on median box size and a
    `band_ratio` multiplier (instead of a fixed pixel threshold).

    Args:
        coords_text_list: list of (bbox, text) where bbox is (x1,y1,x2,y2)
        direction: reading direction (same semantics as group_items_into_lines)
        band_ratio: multiplier for the adaptive band used to group items

    Returns:
        flattened list of (bbox, text) in reading order
    """
    if not coords_text_list:
        return []

    # Build list of bbox items and a mapping to preserve original texts
    bboxes = []
    mapping = defaultdict(deque)  # bbox_tuple -> deque of texts (preserve duplicates)
    for bbox, text in coords_text_list:
        bbox_t = tuple(int(v) for v in bbox)
        bboxes.append(bbox_t)
        mapping[bbox_t].append(text)

    # Use the canonical grouping implementation
    lines = group_items_into_lines(bboxes, direction=direction, band_ratio=band_ratio)

    # Flatten using the mapping to reattach texts in the original multiplicity/order
    out = []
    for line in lines:
        for bbox in line:
            bbox_t = tuple(int(v) for v in bbox)
            if mapping[bbox_t]:
                text = mapping[bbox_t].popleft()
            else:
                text = ''
            out.append((bbox_t, text))

    return out

def visualize_textblocks(canvas, blk_list: List[TextBlock]):
    """Visualize text blocks using PIL."""
    # Convert numpy array to PIL Image
    if isinstance(canvas, np.ndarray):
        if canvas.dtype != np.uint8:
            canvas = canvas.astype(np.uint8)
        if len(canvas.shape) == 3:
            pil_image = Image.fromarray(canvas)
        else:
            pil_image = Image.fromarray(canvas, mode='L').convert('RGB')
    else:
        pil_image = canvas
    
    draw = ImageDraw.Draw(pil_image)
    lw = max(round(sum(canvas.shape) / 2 * 0.003), 2)  # line width
    
    for i, blk in enumerate(blk_list):
        bx1, by1, bx2, by2 = blk.xyxy
        # Draw rectangle
        draw.rectangle([bx1, by1, bx2, by2], outline=(127, 255, 127), width=lw)
        
        # Draw line numbers and polygons (simplified)
        for j, line in enumerate(blk.lines):
            if len(line) > 0:
                draw.text(line[0], str(j), fill=(255, 127, 0))
                # Draw polygon outline (simplified as lines between points)
                if len(line) > 1:
                    for k in range(len(line)):
                        start_point = tuple(line[k])
                        end_point = tuple(line[(k + 1) % len(line)])
                        draw.line([start_point, end_point], fill=(0, 127, 255), width=2)
        
        # Draw block index
        draw.text((bx1, by1 + lw), str(i), fill=(255, 127, 127))
    
    # Convert back to numpy array
    return np.array(pil_image)

def visualize_speech_bubbles(canvas, blk_list: List[TextBlock]):
    """Visualize speech bubbles using PIL."""
    # Convert numpy array to PIL Image
    if isinstance(canvas, np.ndarray):
        if canvas.dtype != np.uint8:
            canvas = canvas.astype(np.uint8)
        if len(canvas.shape) == 3:
            pil_image = Image.fromarray(canvas)
        else:
            pil_image = Image.fromarray(canvas, mode='L').convert('RGB')
    else:
        pil_image = canvas
    
    draw = ImageDraw.Draw(pil_image)
    lw = max(round(sum(canvas.shape) / 2 * 0.003), 2)  # line width

    # Define a color for each class
    class_colors = {
        'text_free': (255, 0, 0),   # Red color for text_free
        'text_bubble': (0, 255, 0),   # Green color for text_bubble
    }

    for blk in blk_list:
        if blk.bubble_xyxy is not None:
            bx1, by1, bx2, by2 = blk.bubble_xyxy

            # Select the color for the current class
            color = class_colors.get(blk.text_class, (127, 255, 127))  # Default color if class not found

            # Draw the bounding box with the selected color
            draw.rectangle([bx1, by1, bx2, by2], outline=color, width=lw)

    # Convert back to numpy array
    return np.array(pil_image)

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

def lists_to_blk_list(blk_list: list[TextBlock], texts_bboxes: list, texts_string: list):  
    group = list(zip(texts_bboxes, texts_string))  

    for blk in blk_list:
        blk_entries = []
        
        for line, text in group:
            if does_rectangle_fit(blk.xyxy, line):
                blk_entries.append((line, text)) 
            elif is_mostly_contained(blk.xyxy, line, 0.5):
                blk_entries.append((line, text)) 

        # Sort and join text entries
        sorted_entries = sort_textblock_rectangles(blk_entries, blk.source_lang_direction)
        
        if is_no_space_lang(blk.source_lang):
            blk.text = ''.join(text for bbox, text in sorted_entries)
        else:
            blk.text = ' '.join(text for bbox, text in sorted_entries)

    return blk_list

