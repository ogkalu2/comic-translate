import numpy as np
import base64
import imkit as imk
from PySide6.QtGui import QColor
from typing import Any

from modules.utils.textblock import TextBlock
from modules.detection.utils.content import get_inpaint_mask


def build_bubble_clip_mask(
    mask_shape: tuple[int, int],
    bounds: tuple[int, int, int, int],
    bubble_xyxy,
    *,
    inset: int,
    image: np.ndarray | None = None,
    seed_bbox: tuple[int, int, int, int] | None = None,
) -> np.ndarray | None:
    if bubble_xyxy is None or len(bubble_xyxy) < 4:
        return None

    x1, y1, x2, y2 = [int(v) for v in bounds]
    bx1, by1, bx2, by2 = [int(v) for v in bubble_xyxy[:4]]
    
    # Calculate relative coordinates for fallback ellipse
    bx1_rel = bx1 + inset - x1
    by1_rel = by1 + inset - y1
    bx2_rel = bx2 - inset - x1
    by2_rel = by2 - inset - y1

    height, width = mask_shape[:2]
    
    use_fallback = True
    
    if image is not None:
        try:
            # Let's perform bubble segmentation!
            H, W = image.shape[:2]
            
            # Crop bubble region with a safety margin to avoid boundary effects
            margin = 5
            crop_y1 = max(0, by1 - margin)
            crop_y2 = min(H, by2 + margin)
            crop_x1 = max(0, bx1 - margin)
            crop_x2 = min(W, bx2 + margin)
            
            bubble_crop = image[crop_y1:crop_y2, crop_x1:crop_x2]
            
            # Convert to grayscale
            if bubble_crop.ndim == 3:
                gray = (0.299 * bubble_crop[..., 2] + 0.587 * bubble_crop[..., 1] + 0.114 * bubble_crop[..., 0]).astype(np.uint8)
            else:
                gray = bubble_crop.copy()
                
            # Define seed region relative to crop
            if seed_bbox is not None:
                sx1, sy1, sx2, sy2 = [int(v) for v in seed_bbox[:4]]
            else:
                # Fallback seed to center of bubble
                sx1 = (bx1 + bx2) // 2 - 5
                sx2 = (bx1 + bx2) // 2 + 5
                sy1 = (by1 + by2) // 2 - 5
                sy2 = (by1 + by2) // 2 + 5
                
            seed_y1_rel = max(0, sy1 - crop_y1)
            seed_y2_rel = min(crop_y2 - crop_y1, sy2 - crop_y1)
            seed_x1_rel = max(0, sx1 - crop_x1)
            seed_x2_rel = min(crop_x2 - crop_x1, sx2 - crop_x1)
            
            seed_region = gray[seed_y1_rel:seed_y2_rel, seed_x1_rel:seed_x2_rel]
            
            if seed_region.size > 0:
                # Find the dominant background color inside the seed area
                hist, bin_edges = np.histogram(seed_region, bins=16, range=(0, 256))
                max_bin = np.argmax(hist)
                bg_val = (bin_edges[max_bin] + bin_edges[max_bin+1]) / 2.0
                
                tolerance = 20
                bg_mask = np.abs(gray - bg_val) <= tolerance
                
                num_labels, labeled = imk.connected_components(bg_mask, connectivity=4)
                
                # Find all labels that appear in the seed_bbox
                seed_pixels_mask = bg_mask[seed_y1_rel:seed_y2_rel, seed_x1_rel:seed_x2_rel]
                seed_labels = labeled[seed_y1_rel:seed_y2_rel, seed_x1_rel:seed_x2_rel][seed_pixels_mask]
                unique_labels = np.unique(seed_labels)
                unique_labels = unique_labels[unique_labels > 0]
                
                if unique_labels.size > 0:
                    bubble_mask = np.isin(labeled, unique_labels)
                    
                    # The bubble box inside the crop is at:
                    b_y1_rel = by1 - crop_y1
                    b_y2_rel = by2 - crop_y1
                    b_x1_rel = bx1 - crop_x1
                    b_x2_rel = bx2 - crop_x1
                    
                    # Extract border pixels of the segmented bubble mask to check touch ratio
                    border_mask_pixels = []
                    if 0 <= b_y1_rel < bubble_mask.shape[0]:
                        border_mask_pixels.extend(bubble_mask[b_y1_rel, max(0, b_x1_rel):min(bubble_mask.shape[1], b_x2_rel)])
                    if 0 <= b_y2_rel - 1 < bubble_mask.shape[0]:
                        border_mask_pixels.extend(bubble_mask[b_y2_rel - 1, max(0, b_x1_rel):min(bubble_mask.shape[1], b_x2_rel)])
                    if 0 <= b_x1_rel < bubble_mask.shape[1]:
                        border_mask_pixels.extend(bubble_mask[max(0, b_y1_rel):min(bubble_mask.shape[0], b_y2_rel), b_x1_rel])
                    if 0 <= b_x2_rel - 1 < bubble_mask.shape[1]:
                        border_mask_pixels.extend(bubble_mask[max(0, b_y1_rel):min(bubble_mask.shape[0], b_y2_rel), b_x2_rel - 1])
                        
                    border_mask_pixels = np.array(border_mask_pixels)
                    if border_mask_pixels.size > 0:
                        touch_ratio = np.mean(border_mask_pixels)
                    else:
                        touch_ratio = 0.0
                        
                    # If the segmented mask touches more than 50% of the bubble border,
                    # it means it leaked to the outside (no outline/boundary contained it).
                    if touch_ratio < 0.5:
                        use_fallback = False
                        
                    if not use_fallback:
                        # Fill holes to include text and ink inside the bubble
                        bubble_mask = imk.close_holes(bubble_mask)
                        
                        # Apply inset by eroding the mask. For the segmented path, we cap the
                        # inset to 2 pixels to keep the mask close to the outline without touching it.
                        seg_inset = min(2, inset)
                        if seg_inset > 0:
                            struct_elem = imk.get_structuring_element(imk.MORPH_CROSS, (3, 3))
                            bubble_mask = imk.erode(bubble_mask.astype(np.uint8) * 255, struct_elem, iterations=seg_inset) > 0
                            
                        # Now map back to the coordinate space of bounds
                        final_clip = np.zeros(mask_shape, dtype=bool)
                        
                        # Calculate overlap between bounds and crop
                        overlap_y1 = max(y1, crop_y1)
                        overlap_y2 = min(y2, crop_y2)
                        overlap_x1 = max(x1, crop_x1)
                        overlap_x2 = min(x2, crop_x2)
                        
                        if overlap_y2 > overlap_y1 and overlap_x2 > overlap_x1:
                            # slice in final_clip
                            f_y1 = overlap_y1 - y1
                            f_y2 = overlap_y2 - y1
                            f_x1 = overlap_x1 - x1
                            f_x2 = overlap_x2 - x1
                            
                            # slice in bubble_mask
                            b_y1 = overlap_y1 - crop_y1
                            b_y2 = overlap_y2 - crop_y1
                            b_x1 = overlap_x1 - crop_x1
                            b_x2 = overlap_x2 - crop_x1
                            
                            final_clip[f_y1:f_y2, f_x1:f_x2] = bubble_mask[b_y1:b_y2, b_x1:b_x2]
                            
                        return final_clip
        except Exception as e:
            # Fall back to ellipse on any error
            pass

    cy_grid, cx_grid = np.ogrid[:height, :width]
    ellipse_cx = (bx1_rel + bx2_rel) / 2.0
    ellipse_cy = (by1_rel + by2_rel) / 2.0
    rx = max(1.0, (bx2_rel - bx1_rel) / 2.0)
    ry = max(1.0, (by2_rel - by1_rel) / 2.0)
    return (((cx_grid - ellipse_cx) / rx) ** 2 + ((cy_grid - ellipse_cy) / ry) ** 2) <= 1.0


def clip_mask_to_bubble(
    mask: np.ndarray,
    bounds: tuple[int, int, int, int],
    bubble_xyxy,
    *,
    inset: int,
    image: np.ndarray | None = None,
    seed_bbox=None,
) -> np.ndarray:
    bubble_clip = build_bubble_clip_mask(
        mask.shape[:2],
        bounds,
        bubble_xyxy,
        inset=inset,
        image=image,
        seed_bbox=seed_bbox,
    )
    if bubble_clip is None:
        return mask
    return np.where(bubble_clip, mask, 0).astype(mask.dtype, copy=False)

def clip_mask_components_to_bubble(
    mask: np.ndarray,
    bounds: tuple[int, int, int, int],
    bubble_xyxy,
    *,
    inset: int,
    image: np.ndarray | None = None,
    seed_bbox=None,
    dilate_kernel_size: int = 0,
    dilate_iterations: int = 1,
) -> np.ndarray:
    """
    Clips a mask to a speech bubble by filtering connected components.
    
    1. Builds the bubble clip mask.
    2. Labels the connected components of the input mask.
    3. Keeps only components that overlap with the bubble clip mask (fully preserving their pixels).
    4. If dilate_kernel_size > 0, dilates the kept components and clips the dilated area to the bubble clip mask
       while unioning/preserving the original undilated kept components.
    """
    bubble_clip = build_bubble_clip_mask(
        mask.shape[:2],
        bounds,
        bubble_xyxy,
        inset=inset,
        image=image,
        seed_bbox=seed_bbox,
    )
    if bubble_clip is None:
        if dilate_kernel_size > 0:
            dil_kernel = np.ones((dilate_kernel_size, dilate_kernel_size), np.uint8)
            return imk.dilate(mask, dil_kernel, iterations=dilate_iterations)
        return mask

    num_labels, labeled_text = imk.connected_components(mask > 0, connectivity=4)
    overlapping_labels = np.unique(labeled_text[bubble_clip])
    keep_labels = overlapping_labels[overlapping_labels > 0]

    if keep_labels.size == 0:
        return np.zeros_like(mask)

    kept_mask = np.isin(labeled_text, keep_labels)

    if dilate_kernel_size > 0:
        dil_kernel = np.ones((dilate_kernel_size, dilate_kernel_size), np.uint8)
        dilated = imk.dilate(kept_mask.astype(np.uint8) * 255, dil_kernel, iterations=dilate_iterations)
        final_mask = np.where(bubble_clip, dilated, 0).astype(np.uint8)
        return np.bitwise_or(final_mask, (kept_mask * 255).astype(np.uint8)).astype(mask.dtype, copy=False)
    else:
        return (kept_mask * 255).astype(mask.dtype, copy=False)

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
    clip_to_bubble: bool = False,
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

    if clip_to_bubble and getattr(blk, "text_class", None) == "text_bubble" and getattr(blk, "bubble_xyxy", None) is not None:
        inset = max(1, kernel_size)
        dilated_crop_mask = clip_mask_components_to_bubble(
            crop_mask,
            (cx1, cy1, cx2, cy2),
            blk.bubble_xyxy,
            inset=inset,
            image=img,
            seed_bbox=blk.xyxy,
            dilate_kernel_size=kernel_size,
            dilate_iterations=dilate_iterations,
        )
    else:
        dil_kernel = np.ones((kernel_size, kernel_size), np.uint8)
        dilated_crop_mask = imk.dilate(crop_mask, dil_kernel, iterations=dilate_iterations)

    return dilated_crop_mask, (cx1, cy1, cx2, cy2)



def collect_block_mask_data(
    img: np.ndarray,
    blk_list: list[TextBlock],
    default_padding: int = 5,
    require_text_or_translation: bool = True,
    clip_to_bubble: bool = True,
) -> list[dict[str, Any]]:
    entries: list[dict[str, Any]] = []
    for blk in blk_list:
        crop_mask, bounds = build_block_mask_data(
            img,
            blk,
            default_padding=default_padding,
            require_text_or_translation=require_text_or_translation,
            clip_to_bubble=clip_to_bubble,
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
