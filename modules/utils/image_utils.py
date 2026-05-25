import numpy as np
import base64
import imkit as imk
from PySide6.QtGui import QColor

from modules.utils.textblock import TextBlock
from modules.detection.utils.content import get_inpaint_mask

def rgba2hex(rgba_list):
    r,g,b,a = [int(num) for num in rgba_list]
    return "#{:02x}{:02x}{:02x}{:02x}".format(r, g, b, a)

def encode_image_array(img_array: np.ndarray):
    img_bytes = imk.encode_image(img_array, ".png")
    return base64.b64encode(img_bytes).decode('utf-8')

def get_smart_text_color(
    detected_color: tuple|str,
    setting_color: QColor
    ) -> QColor:
    """
    Determines the best text color to use based on the detected color from the image
    and the user's preferred setting color.

    Policy:
      - If detection succeeded, use the detected colour (it came from
        actual pixel analysis and is most likely correct).
      - If detection is empty / invalid, fall back to the user setting.
    """
    if not detected_color:
        return setting_color

    try:
        if isinstance(detected_color, str):
            detected_color = QColor(detected_color)
        else:
            detected_color = QColor(*detected_color)
        if not detected_color.isValid():
            return setting_color

        return detected_color

    except Exception:
        pass

    return setting_color

def generate_mask(img: np.ndarray, blk_list: list[TextBlock], default_padding: int = 5) -> np.ndarray:
    """
    Generate a text-removal mask from filtered connected components and
    only lightly expand it to catch antialiasing around glyph edges.
    """
    from modules.utils.textblock import adjust_text_line_coordinates
    from modules.detection.utils.content import detect_content_mask_in_bbox, filter_and_fix_bboxes
    
    h, w, _ = img.shape
    mask = np.zeros((h, w), dtype=np.uint8)

    for blk in blk_list:
        # Skip blocks with no text and no translation
        if not blk.text and not blk.translation:
            continue
        
        # Get the padded coordinates to crop the image
        cx1, cy1, cx2, cy2 = adjust_text_line_coordinates(blk.xyxy, 10, 10, img)
        crop = img[cy1:cy2, cx1:cx2]
        
        crop_mask = detect_content_mask_in_bbox(crop)
        if crop_mask is None or not np.any(crop_mask):
            continue
        # Bridge tiny fractures without collapsing whole lines into slabs.
        close_kernel = imk.get_structuring_element(imk.MORPH_RECT, (3, 3))
        crop_mask = imk.morphology_ex(crop_mask, imk.MORPH_CLOSE, close_kernel)

        # 8) Determine dilation kernel size
        kernel_size = default_padding
        src_lang = getattr(blk, 'source_lang', None)
        if src_lang and src_lang not in ['ja', 'ko']:
            kernel_size = 3
        dilate_iterations = 1
        
        # Keep mask inside bubble interiors when bubble bounds are available.
        if getattr(blk, 'text_class', None) == 'text_bubble' and getattr(blk, 'bubble_xyxy', None) is not None:
            bx1, by1, bx2, by2 = [int(v) for v in blk.bubble_xyxy]
            inset = max(1, kernel_size)
            ix1 = max(0, min(cx2 - cx1, bx1 + inset - cx1))
            iy1 = max(0, min(cy2 - cy1, by1 + inset - cy1))
            ix2 = max(ix1, min(cx2 - cx1, bx2 - inset - cx1))
            iy2 = max(iy1, min(cy2 - cy1, by2 - inset - cy1))
            
            bubble_clip = np.zeros(crop_mask.shape[:2], dtype=np.uint8)
            bubble_clip[iy1:iy2, ix1:ix2] = 255
            crop_mask = np.bitwise_and(crop_mask, bubble_clip)

        # 9) Dilate the block mask
        dil_kernel = np.ones((kernel_size, kernel_size), np.uint8)
        dilated_crop_mask = imk.dilate(crop_mask, dil_kernel, iterations=dilate_iterations)

        # 10) Combine with global mask
        mask[cy1:cy2, cx1:cx2] = np.bitwise_or(mask[cy1:cy2, cx1:cx2], dilated_crop_mask)

    return mask
