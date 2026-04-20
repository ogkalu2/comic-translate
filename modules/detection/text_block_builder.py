import numpy as np

from ..utils.textblock import TextBlock
from .font.engine import FontEngineFactory
from .utils.content import filter_and_fix_bboxes
from .utils.geometry import (
    does_rectangle_fit,
    do_rectangles_overlap,
    merge_overlapping_boxes,
)


def _detect_font_attributes(settings, image: np.ndarray, txt_box: np.ndarray, txt_idx: int) -> dict:
    font_attrs = {}

    try:
        x1, y1, x2, y2 = map(int, txt_box)
        h, w = image.shape[:2]
        x1 = max(0, x1)
        y1 = max(0, y1)
        x2 = min(w, x2)
        y2 = min(h, y2)

        if x2 > x1 and y2 > y1:
            crop = image[y1:y2, x1:x2]
            font_engine = FontEngineFactory.create_engine(settings, backend='onnx')
            font_attrs = font_engine.process(crop)
    except Exception as e:
        print(f"Failed to detect font attributes for text block {txt_idx}: {e}")

    return font_attrs


def _make_text_block(
    txt_box: np.ndarray,
    *,
    text_class: str,
    bubble_box: np.ndarray | None = None,
    font_attrs: dict | None = None,
) -> TextBlock:
    font_attrs = font_attrs or {}
    font_size_px = float(font_attrs.get('font_size_px') or 0.0)

    return TextBlock(
        text_bbox=txt_box,
        bubble_bbox=bubble_box,
        text_class=text_class,
        direction=font_attrs.get('direction', ''),
        font_color=tuple(font_attrs.get('text_color', ())),
        font_size_px=font_size_px,
        max_font_size=int(round(font_size_px)) if font_size_px > 0 else 0,
    )


def create_text_blocks(
    settings,
    image: np.ndarray,
    text_boxes: np.ndarray,
    bubble_boxes: np.ndarray | None = None,
) -> list[TextBlock]:
    text_boxes = filter_and_fix_bboxes(text_boxes, image.shape)
    if bubble_boxes is None:
        bubble_boxes = np.empty((0, 4), dtype=int)
    else:
        bubble_boxes = filter_and_fix_bboxes(bubble_boxes, image.shape)
    text_boxes = merge_overlapping_boxes(text_boxes)

    text_blocks: list[TextBlock] = []
    text_matched = [False] * len(text_boxes)

    for txt_idx, txt_box in enumerate(text_boxes):
        font_attrs = _detect_font_attributes(settings, image, txt_box, txt_idx)

        if len(bubble_boxes) == 0:
            text_blocks.append(
                _make_text_block(txt_box, text_class='text_free', font_attrs=font_attrs)
            )
            continue

        for bble_box in bubble_boxes:
            if bble_box is None:
                continue
            if does_rectangle_fit(bble_box, txt_box) or do_rectangles_overlap(bble_box, txt_box):
                text_blocks.append(
                    _make_text_block(
                        txt_box,
                        text_class='text_bubble',
                        bubble_box=bble_box,
                        font_attrs=font_attrs,
                    )
                )
                text_matched[txt_idx] = True
                break

        if not text_matched[txt_idx]:
            text_blocks.append(
                _make_text_block(txt_box, text_class='text_free', font_attrs=font_attrs)
            )

    return text_blocks
