import numpy as np
import base64
import imkit as imk
from PySide6.QtGui import QColor
from typing import Any

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

def build_block_mask_data(
    img: np.ndarray,
    blk: TextBlock,
    default_padding: int = 5,
    require_text_or_translation: bool = True,
) -> tuple[np.ndarray | None, tuple[int, int, int, int] | None]:
    from modules.utils.textblock import adjust_text_line_coordinates
    from modules.detection.utils.content import detect_content_mask_in_bbox

    if require_text_or_translation and not blk.text and not blk.translation:
        return None, None

    cx1, cy1, cx2, cy2 = adjust_text_line_coordinates(blk.xyxy, 10, 10, img)
    crop = img[cy1:cy2, cx1:cx2]

    crop_mask = detect_content_mask_in_bbox(crop)
    if crop_mask is None or not np.any(crop_mask):
        return None, None

    close_kernel = imk.get_structuring_element(imk.MORPH_RECT, (3, 3))
    crop_mask = imk.morphology_ex(crop_mask, imk.MORPH_CLOSE, close_kernel)

    kernel_size = default_padding
    dilate_iterations = 3

    if getattr(blk, "text_class", None) == "text_bubble" and getattr(blk, "bubble_xyxy", None) is not None:
        bx1, by1, bx2, by2 = [int(v) for v in blk.bubble_xyxy]
        inset = max(1, kernel_size)
        bx1_rel = bx1 + inset - cx1
        by1_rel = by1 + inset - cy1
        bx2_rel = bx2 - inset - cx1
        by2_rel = by2 - inset - cy1

        h_crop, w_crop = crop_mask.shape[:2]
        cy_grid, cx_grid = np.ogrid[:h_crop, :w_crop]
        ellipse_cx = (bx1_rel + bx2_rel) / 2.0
        ellipse_cy = (by1_rel + by2_rel) / 2.0
        rx = max(1.0, (bx2_rel - bx1_rel) / 2.0)
        ry = max(1.0, (by2_rel - by1_rel) / 2.0)
        
        bubble_clip = (((cx_grid - ellipse_cx) / rx) ** 2 + ((cy_grid - ellipse_cy) / ry) ** 2) <= 1.0
        crop_mask = np.where(bubble_clip, crop_mask, 0).astype(np.uint8)

    dil_kernel = np.ones((kernel_size, kernel_size), np.uint8)
    dilated_crop_mask = imk.dilate(crop_mask, dil_kernel, iterations=dilate_iterations)
    return dilated_crop_mask, (cx1, cy1, cx2, cy2)


def collect_block_mask_data(
    img: np.ndarray,
    blk_list: list[TextBlock],
    default_padding: int = 5,
    require_text_or_translation: bool = True,
) -> list[dict[str, Any]]:
    entries: list[dict[str, Any]] = []
    for blk in blk_list:
        crop_mask, bounds = build_block_mask_data(
            img,
            blk,
            default_padding=default_padding,
            require_text_or_translation=require_text_or_translation,
        )
        if crop_mask is None or bounds is None:
            continue
        entries.append({"block": blk, "mask": crop_mask, "bounds": bounds})
    return entries


def generate_mask(img: np.ndarray, blk_list: list[TextBlock], default_padding: int = 5) -> np.ndarray:
    """
    Generate a text-removal mask from filtered connected components and
    only lightly expand it to catch antialiasing around glyph edges.
    """
    h, w, _ = img.shape
    mask = np.zeros((h, w), dtype=np.uint8)

    for entry in collect_block_mask_data(img, blk_list, default_padding=default_padding):
        cx1, cy1, cx2, cy2 = entry["bounds"]
        crop_mask = entry["mask"]
        mask[cy1:cy2, cx1:cx2] = np.bitwise_or(mask[cy1:cy2, cx1:cx2], crop_mask)

    return mask
