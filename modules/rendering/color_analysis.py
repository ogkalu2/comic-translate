"""Colour sampling routines for Torii-style auto rendering."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional, Sequence, Tuple

import mahotas as mh
import numpy as np

from modules.layout.grouping import TextGroup
from modules.utils.masks import dilate, erode, polygon_to_mask, ring
from modules.utils.wcag import relative_luminance

ColorTuple = Tuple[int, int, int]


@dataclass
class ColorAnalysis:
    fill_rgb: Optional[ColorTuple]
    stroke_rgb: Optional[ColorTuple]
    background_rgb: Optional[ColorTuple]
    fill_luminance: Optional[float]
    stroke_luminance: Optional[float]
    background_luminance: Optional[float]
    plain_white: bool
    plain_black: bool
    core_pixel_count: int
    stroke_pixel_count: int
    background_pixel_count: int


def _median_rgb(values: np.ndarray) -> Optional[ColorTuple]:
    if values.size == 0:
        return None
    reshaped = values.reshape(-1, values.shape[-1])
    med = np.median(reshaped, axis=0)
    return tuple(int(round(v)) for v in med)


def _auto_threshold(gray: np.ndarray) -> float:
    flat = gray.reshape(-1)
    if flat.size == 0:
        return 0.0
    return float(mh.thresholding.otsu(flat.astype(np.uint8)))


def _choose_text_mask(gray: np.ndarray, polygon_mask: np.ndarray) -> np.ndarray:
    interior_pixels = gray[polygon_mask]
    if interior_pixels.size == 0:
        return np.zeros_like(gray, dtype=bool)

    threshold = _auto_threshold(interior_pixels)
    darker = np.logical_and(gray <= threshold, polygon_mask)
    lighter = np.logical_and(gray >= threshold, polygon_mask)

    candidate = darker if darker.sum() >= lighter.sum() else lighter
    if candidate.sum() == 0:
        return candidate

    # Use a quick morphological close to patch small gaps so erosion works better.
    closed = dilate(candidate, 1)
    closed = np.logical_and(erode(closed, 1), polygon_mask)
    return closed if closed.sum() > 0 else candidate


def analyse_group_colors(
    image: np.ndarray,
    group: TextGroup,
    ring_radius: int = 6,
    min_core_pixels: int = 50,
) -> Optional[ColorAnalysis]:
    if image is None or image.size == 0:
        return None

    minx, miny, maxx, maxy = group.bbox
    pad = max(ring_radius + 2, 4)
    h, w = image.shape[:2]
    x1 = max(0, minx - pad)
    y1 = max(0, miny - pad)
    x2 = min(w, maxx + pad)
    y2 = min(h, maxy + pad)
    if x2 <= x1 or y2 <= y1:
        return None

    patch = image[y1:y2, x1:x2]
    poly = np.asarray(group.polygon, dtype=np.float32)
    if poly.size == 0:
        return None
    local_poly = [(float(x) - x1, float(y) - y1) for x, y in poly]
    mask = polygon_to_mask((patch.shape[0], patch.shape[1]), local_poly)
    if not mask.any():
        return None

    gray = np.dot(patch[..., :3], [0.299, 0.587, 0.114])
    text_mask = _choose_text_mask(gray, mask)

    core = erode(text_mask, 1)
    if core.sum() < min_core_pixels:
        core = erode(text_mask, 0)

    stroke_ring = np.logical_and(text_mask, np.logical_not(core))
    if stroke_ring.sum() < min_core_pixels // 4:
        expanded = dilate(text_mask, 1)
        stroke_ring = np.logical_and(expanded, np.logical_not(core))

    background_ring = ring(mask, 0, ring_radius)
    text_guard = dilate(text_mask, 1)
    background_ring = np.logical_and(background_ring, np.logical_not(text_guard))
    if background_ring.sum() < min_core_pixels:
        background_ring = ring(mask, 1, max(ring_radius, 3))
        background_ring = np.logical_and(background_ring, np.logical_not(text_guard))

    fill_rgb = _median_rgb(patch[core])
    stroke_rgb = _median_rgb(patch[stroke_ring]) if stroke_ring.any() else None
    bg_rgb = _median_rgb(patch[background_ring]) if background_ring.any() else None

    fill_lum = relative_luminance(fill_rgb) if fill_rgb else None
    stroke_lum = relative_luminance(stroke_rgb) if stroke_rgb else None
    bg_lum = relative_luminance(bg_rgb) if bg_rgb else None

    plain_white = False
    plain_black = False
    if bg_rgb is not None:
        bg_pixels = patch[background_ring]
        if bg_pixels.size:
            bg_float = bg_pixels.reshape(-1, 3).astype(np.float32) / 255.0
            mean = float(np.mean(bg_float))
            var = float(np.var(bg_float))
            plain_white = mean > 0.94 and var < 0.002
            plain_black = mean < 0.06 and var < 0.002

    return ColorAnalysis(
        fill_rgb=fill_rgb,
        stroke_rgb=stroke_rgb,
        background_rgb=bg_rgb,
        fill_luminance=fill_lum,
        stroke_luminance=stroke_lum,
        background_luminance=bg_lum,
        plain_white=plain_white,
        plain_black=plain_black,
        core_pixel_count=int(core.sum()),
        stroke_pixel_count=int(stroke_ring.sum()),
        background_pixel_count=int(background_ring.sum()),
    )


__all__ = ["ColorAnalysis", "analyse_group_colors"]
