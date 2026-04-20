import numpy as np
import base64
import imkit as imk
from PySide6.QtGui import QColor

from modules.utils.textblock import TextBlock
from modules.detection.utils.content import get_inpaint_bboxes
from modules.utils.language_utils import is_no_space_text

def rgba2hex(rgba_list):
    r,g,b,a = [int(num) for num in rgba_list]
    return "#{:02x}{:02x}{:02x}{:02x}".format(r, g, b, a)

def encode_image_array(img_array: np.ndarray):
    img_bytes = imk.encode_image(img_array, ".png")
    return base64.b64encode(img_bytes).decode('utf-8')

def get_smart_text_color(detected_rgb: tuple, setting_color: QColor) -> QColor:
    """
    Determines the best text color to use based on the detected color from the image
    and the user's preferred setting color.

    Policy:
      - If detection succeeded, use the detected colour (it came from
        actual pixel analysis and is most likely correct).
      - If detection is empty / invalid, fall back to the user setting.
    """
    if not detected_rgb:
        return setting_color

    try:
        detected_color = QColor(*detected_rgb)
        if not detected_color.isValid():
            return setting_color

        return detected_color

    except Exception:
        pass

    return setting_color

def generate_mask(img: np.ndarray, blk_list: list[TextBlock], default_padding: int = 5) -> np.ndarray:
    """
    Generate a mask by fitting a merged shape around each block's inpaint bboxes,
    then dilating that shape according to padding logic.
    """
    h, w, _ = img.shape
    mask = np.zeros((h, w), dtype=np.uint8)
    LONG_EDGE = 2048

    for blk in blk_list:
        # Skip blocks with no text and no translation
        if not blk.text and not blk.translation:
            continue

        bboxes = getattr(blk, "inpaint_bboxes", None)
        if bboxes is None or len(bboxes) == 0:
            if getattr(blk, "xyxy", None) is None:
                continue
            bboxes = get_inpaint_bboxes(blk.xyxy, img)
            blk.inpaint_bboxes = bboxes
        else:
            bboxes = np.asarray(bboxes, dtype=np.int32)
            blk.inpaint_bboxes = bboxes
        if bboxes is None or len(bboxes) == 0:
            continue

        # 1) Compute tight per-block ROI
        xs = [x for x1, _, x2, _ in bboxes for x in (x1, x2)]
        ys = [y for _, y1, _, y2 in bboxes for y in (y1, y2)]
        min_x, max_x = int(min(xs)), int(max(xs))
        min_y, max_y = int(min(ys)), int(max(ys))
        roi_w, roi_h = max_x - min_x + 1, max_y - min_y + 1

        # 2) Down-sample factor to limit mask size
        ds = max(1.0, max(roi_w, roi_h) / LONG_EDGE)
        mw, mh = int(roi_w / ds) + 2, int(roi_h / ds) + 2
        pad_offset = 1

        # 3) Paint bboxes into small mask with padding offset
        small = np.zeros((mh, mw), dtype=np.uint8)
        for x1, y1, x2, y2 in bboxes:
            x1i = int((x1 - min_x) / ds) + pad_offset
            y1i = int((y1 - min_y) / ds) + pad_offset
            x2i = int((x2 - min_x) / ds) + pad_offset
            y2i = int((y2 - min_y) / ds) + pad_offset
            small = imk.rectangle(small, (x1i, y1i), (x2i, y2i), 255, -1)

        # 4) Close small mask to bridge gaps
        KSIZE = 15
        kernel = imk.get_structuring_element(imk.MORPH_RECT, (KSIZE, KSIZE))
        closed = imk.morphology_ex(small, imk.MORPH_CLOSE, kernel)

        # 5) Extract all contours
        contours, _ = imk.find_contours(closed)
        if not contours:
            continue

        # 6) Merge contours: collect valid polygons in full image coords
        polys = []
        for cnt in contours:
            pts = cnt.squeeze(1)
            if pts.ndim != 2 or pts.shape[0] < 3:
                continue
            pts_f = (pts.astype(np.float32) - pad_offset) * ds
            pts_f[:, 0] += min_x
            pts_f[:, 1] += min_y
            polys.append(pts_f.astype(np.int32))
        if not polys:
            continue

        # 8) Determine dilation kernel size
        kernel_size = default_padding
        text_probe = getattr(blk, 'translation', '') or getattr(blk, 'text', '')
        if text_probe and not is_no_space_text(text_probe):
            kernel_size = 3
        # Adjust for text bubbles: only consider contours wholly inside the bubble
        if getattr(blk, 'text_class', None) == 'text_bubble' and getattr(blk, 'bubble_xyxy', None) is not None:
            bx1, by1, bx2, by2 = blk.bubble_xyxy
            # filter polygons fully within bubble bounds
            valid = [p for p in polys 
                     if (p[:,0] >= bx1).all() and (p[:,0] <= bx2).all() 
                     and (p[:,1] >= by1).all() and (p[:,1] <= by2).all()]
            if valid:
                # compute distances for each polygon and get overall minimum
                dists = []
                for p in valid:
                    left   = p[:,0].min() - bx1
                    right  = bx2 - p[:,0].max()
                    top    = p[:,1].min() - by1
                    bottom = by2 - p[:,1].max()
                    dists.extend([left, right, top, bottom])
                min_dist = min(dists)
                if kernel_size >= min_dist:
                    kernel_size = max(1, int(min_dist * 0.8))

        # 9) Fill and dilate only the local ROI for this block instead of the
        # full page. This preserves behavior while avoiding full-image work
        # for every block on large pages.
        poly_min_x = min(int(p[:, 0].min()) for p in polys)
        poly_max_x = max(int(p[:, 0].max()) for p in polys)
        poly_min_y = min(int(p[:, 1].min()) for p in polys)
        poly_max_y = max(int(p[:, 1].max()) for p in polys)

        dilation_pad = max(2, kernel_size * 2 + 2)
        roi_x1 = max(0, poly_min_x - dilation_pad)
        roi_y1 = max(0, poly_min_y - dilation_pad)
        roi_x2 = min(w, poly_max_x + dilation_pad + 1)
        roi_y2 = min(h, poly_max_y + dilation_pad + 1)

        if roi_x1 >= roi_x2 or roi_y1 >= roi_y2:
            continue

        local_polys = []
        for poly in polys:
            local_poly = poly.copy()
            local_poly[:, 0] -= roi_x1
            local_poly[:, 1] -= roi_y1
            local_polys.append(local_poly)

        block_mask = np.zeros((roi_y2 - roi_y1, roi_x2 - roi_x1), dtype=np.uint8)
        block_mask = imk.fill_poly(block_mask, local_polys, 255)

        # 10) Dilate the local block mask
        dil_kernel = np.ones((kernel_size, kernel_size), np.uint8)
        dilated = imk.dilate(block_mask, dil_kernel, iterations=4)

        # 11) Combine with global mask only inside the ROI
        mask_roi = mask[roi_y1:roi_y2, roi_x1:roi_x2]
        np.bitwise_or(mask_roi, dilated, out=mask_roi)

    return mask
