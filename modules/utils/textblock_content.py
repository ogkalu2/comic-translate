from __future__ import annotations

import re
from collections import defaultdict, deque
from typing import TYPE_CHECKING

from ..detection.utils.text_lines import group_items_into_lines
from modules.detection.utils.orientation import infer_text_direction
from modules.detection.utils.geometry import does_rectangle_fit, is_mostly_contained
from modules.utils.language_utils import is_no_space_text

if TYPE_CHECKING:
    from .textblock import TextBlock


def sort_textblock_rectangles(
    coords_text_list: list[tuple[tuple[int, int, int, int], str]],
    direction: str = 'ver_rtl',
    band_ratio: float = 0.5,
) -> list[tuple[tuple[int, int, int, int], str]]:
    """
    Sort a list of (bbox, text) tuples into reading order using the
    shared grouping code in `group_items_into_lines`.
    """
    if not coords_text_list:
        return []

    bboxes = []
    mapping = defaultdict(deque)
    for bbox, text in coords_text_list:
        bbox_t = tuple(int(v) for v in bbox)
        bboxes.append(bbox_t)
        mapping[bbox_t].append(text)

    lines = group_items_into_lines(bboxes, direction=direction, band_ratio=band_ratio)

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


def lists_to_blk_list(blk_list: list[TextBlock], texts_bboxes: list, texts_string: list):
    # (bbox, text) pairs; normalize types
    group = []
    for b, t in zip(texts_bboxes, texts_string):
        if b is None:
            continue
        bbox = tuple(int(v) for v in b)
        if isinstance(t, (tuple, list)):
            t = " ".join(str(x) for x in t if x is not None)
        else:
            t = "" if t is None else str(t)
        group.append((bbox, t))

    def _area(b):
        x1, y1, x2, y2 = b
        return max(0, x2 - x1) * max(0, y2 - y1)

    def _center(b):
        x1, y1, x2, y2 = b
        return ((x1 + x2) * 0.5, (y1 + y2) * 0.5)

    def _iou(a, b):
        ax1, ay1, ax2, ay2 = a
        bx1, by1, bx2, by2 = b
        ix1, iy1 = max(ax1, bx1), max(ay1, by1)
        ix2, iy2 = min(ax2, bx2), min(ay2, by2)
        iw, ih = max(0, ix2 - ix1), max(0, iy2 - iy1)
        inter = iw * ih
        if inter <= 0:
            return 0.0
        ua = _area(a) + _area(b) - inter
        return float(inter) / float(ua) if ua > 0 else 0.0

    _re_has_latin = re.compile(r"[A-Za-z0-9]")
    _re_cjk = re.compile(r"[\u4e00-\u9fff]")

    def _clean_text(s: str) -> str:
        s = (s or "").strip()
        if not s:
            return ""
        low = s.lower()
        if low.startswith("the image is") or low.startswith("this image is") or low.startswith("image is"):
            return ""
        if _re_cjk.search(s) and not _re_has_latin.search(s):
            return ""
        if not _re_has_latin.search(s):
            return ""
        return re.sub(r"\s+", " ", s).strip()

    group = [(b, _clean_text(t)) for (b, t) in group]
    group = [(b, t) for (b, t) in group if t]

    for blk in blk_list:
        blk_entries = []

        for line_bbox, text in group:
            if does_rectangle_fit(blk.xyxy, line_bbox):
                blk_entries.append((line_bbox, text))
            elif is_mostly_contained(blk.xyxy, line_bbox, 0.5):
                blk_entries.append((line_bbox, text))
            elif _iou(tuple(int(v) for v in blk.xyxy), line_bbox) > 0.05:
                blk_entries.append((line_bbox, text))

        if not blk_entries and group:
            bx, by = _center(tuple(int(v) for v in blk.xyxy))
            best = None
            best_d2 = None
            for line_bbox, text in group:
                cx, cy = _center(line_bbox)
                d2 = (cx - bx) ** 2 + (cy - by) ** 2
                if best_d2 is None or d2 < best_d2:
                    best_d2 = d2
                    best = (line_bbox, text)
            if best is not None:
                blk_entries = [best]

        direction = infer_text_direction([bbox for bbox, _ in blk_entries]) if blk_entries else ('ver_rtl' if getattr(blk, "direction", "") == 'vertical' else 'hor_ltr')
        sorted_entries = sort_textblock_rectangles(blk_entries, direction)

        combined_text = ' '.join(text for _, text in sorted_entries).strip()
        if is_no_space_text(combined_text):
            blk.text = ''.join(text for _, text in sorted_entries).strip()
        else:
            blk.text = combined_text

        blk.texts = [text for _, text in sorted_entries if text]

    return blk_list
