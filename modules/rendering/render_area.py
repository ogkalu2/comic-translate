from __future__ import annotations

from modules.detection.utils.geometry import shrink_bbox
from modules.detection.utils.orientation import infer_orientation
from modules.utils.language_utils import is_no_space_text
from modules.utils.textblock import adjust_blks_size


def get_best_render_area(blk_list, img, inpainted_img=None):
    # Using Speech Bubble detection to find best Text Render Area
    for blk in blk_list:
        direction = getattr(blk, "direction", "")
        if hasattr(blk, "render_state"):
            try:
                direction = blk.render_state().direction
            except Exception:
                direction = getattr(blk, "direction", "")

        if blk.text_class == 'text_bubble' and blk.bubble_xyxy is not None:
            if infer_orientation([blk.xyxy]) == 'vertical' or direction == "vertical":
                text_draw_bounds = shrink_bbox(blk.bubble_xyxy, shrink_percent=0.3)
                bdx1, bdy1, bdx2, bdy2 = text_draw_bounds
                blk.xyxy[:] = [bdx1, bdy1, bdx2, bdy2]

    combined_text_parts = []
    for blk in blk_list:
        if hasattr(blk, "content_state"):
            try:
                content_state = blk.content_state()
                if content_state.translation:
                    combined_text_parts.append(content_state.translation)
                if content_state.text:
                    combined_text_parts.append(content_state.text)
                continue
            except Exception:
                pass

        translation = getattr(blk, "translation", "") or ""
        text = getattr(blk, "text", "") or ""
        if translation:
            combined_text_parts.append(translation)
        if text:
            combined_text_parts.append(text)

    combined_text = " ".join(combined_text_parts)
    if blk_list and not is_no_space_text(combined_text):
        adjust_blks_size(blk_list, img, -5, -5)

    return blk_list
