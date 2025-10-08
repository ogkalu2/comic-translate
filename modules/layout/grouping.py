"""Utilities for grouping OCR text blocks into logical clusters."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, List, Sequence, Tuple

import numpy as np
from shapely.geometry import Polygon, box
from shapely.ops import unary_union

from modules.utils.textblock import TextBlock


@dataclass
class TextGroup:
    blocks: List[TextBlock]
    polygon: np.ndarray
    bbox: Tuple[int, int, int, int]


def _block_polygon(block: TextBlock) -> Polygon:
    if block.segm_pts is not None and len(block.segm_pts) >= 6:
        pts = np.asarray(block.segm_pts, dtype=np.float32).reshape(-1, 2)
        return Polygon(pts)
    if block.xyxy is not None and len(block.xyxy) == 4:
        x1, y1, x2, y2 = block.xyxy
        return box(x1, y1, x2, y2)
    raise ValueError("Block lacks sufficient geometry for grouping")


def group_text_blocks(blocks: Sequence[TextBlock]) -> List[TextGroup]:
    """Merge nearby blocks that share a bubble or overlapping area."""

    if not blocks:
        return []

    remaining = list(blocks)
    groups: List[TextGroup] = []

    while remaining:
        blk = remaining.pop(0)
        current = [blk]
        geom = _block_polygon(blk)
        bubble_key = None
        if getattr(blk, "bubble_xyxy", None) is not None:
            bubble_key = tuple(int(v) for v in blk.bubble_xyxy)

        matched = []
        for other in remaining:
            other_key = tuple(int(v) for v in other.bubble_xyxy) if getattr(other, "bubble_xyxy", None) is not None else None
            should_merge = False
            if bubble_key and other_key and bubble_key == other_key:
                should_merge = True
            else:
                try:
                    other_geom = _block_polygon(other)
                except ValueError:
                    continue
                dilated = other_geom.buffer(max(other_geom.length * 0.02, 4.0))
                if geom.buffer(max(geom.length * 0.02, 4.0)).intersects(dilated):
                    should_merge = True
            if should_merge:
                matched.append(other)

        for mt in matched:
            remaining.remove(mt)
            current.append(mt)

        polygons = []
        for blk_member in current:
            try:
                polygons.append(_block_polygon(blk_member))
            except ValueError:
                continue
        if not polygons:
            continue

        merged = unary_union(polygons)
        if merged.geom_type == "Polygon":
            coords = np.array(merged.exterior.coords, dtype=np.float32)
            minx, miny, maxx, maxy = merged.bounds
        else:
            coords = np.array(merged.convex_hull.exterior.coords, dtype=np.float32)
            minx, miny, maxx, maxy = merged.convex_hull.bounds

        groups.append(
            TextGroup(
                blocks=current,
                polygon=coords,
                bbox=(int(minx), int(miny), int(np.ceil(maxx)), int(np.ceil(maxy))),
            )
        )

    return groups


__all__ = ["TextGroup", "group_text_blocks"]
