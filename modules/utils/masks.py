"""Helpers for constructing and manipulating binary masks."""

from __future__ import annotations

from typing import Iterable, Sequence, Tuple

import mahotas as mh
import numpy as np
from PIL import Image, ImageDraw

ArrayLike = np.ndarray


def polygon_to_mask(size: Tuple[int, int], polygon: Sequence[Tuple[float, float]]) -> ArrayLike:
    """Rasterise a polygon into a boolean mask."""

    height, width = size
    if height <= 0 or width <= 0:
        return np.zeros((0, 0), dtype=bool)

    img = Image.new("L", (width, height), 0)
    draw = ImageDraw.Draw(img)
    if polygon:
        draw.polygon(list(polygon), outline=1, fill=1)
    mask = np.array(img, dtype=bool)
    return mask


def dilate(mask: ArrayLike, radius: int = 1) -> ArrayLike:
    if mask.size == 0 or radius <= 0:
        return mask.astype(bool)
    structure = np.ones((radius * 2 + 1, radius * 2 + 1), dtype=bool)
    return mh.dilate(mask.astype(bool), structure)


def erode(mask: ArrayLike, radius: int = 1) -> ArrayLike:
    if mask.size == 0 or radius <= 0:
        return mask.astype(bool)
    structure = np.ones((radius * 2 + 1, radius * 2 + 1), dtype=bool)
    return mh.erode(mask.astype(bool), structure)


def ring(mask: ArrayLike, inner_radius: int, outer_radius: int) -> ArrayLike:
    """Return the ring between two dilation radii."""

    if inner_radius < 0:
        raise ValueError("inner_radius must be non-negative")
    if outer_radius <= inner_radius:
        raise ValueError("outer_radius must be greater than inner_radius")

    inner = dilate(mask, inner_radius) if inner_radius > 0 else mask.astype(bool)
    outer = dilate(mask, outer_radius)
    return np.logical_and(outer, np.logical_not(inner))


def bounds_from_polygon(polygon: Iterable[Tuple[float, float]]) -> Tuple[int, int, int, int]:
    """Compute axis-aligned bounds covering the polygon."""

    xs, ys = zip(*polygon) if polygon else ((0,), (0,))
    x1 = int(np.floor(min(xs)))
    y1 = int(np.floor(min(ys)))
    x2 = int(np.ceil(max(xs)))
    y2 = int(np.ceil(max(ys)))
    return x1, y1, x2, y2


__all__ = [
    "polygon_to_mask",
    "dilate",
    "erode",
    "ring",
    "bounds_from_polygon",
]
