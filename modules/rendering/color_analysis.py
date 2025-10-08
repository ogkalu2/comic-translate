"""Colour sampling routines for Torii-style auto rendering."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional, Sequence, Tuple

import mahotas as mh
import numpy as np

from modules.layout.grouping import TextGroup
from modules.utils.textblock import TextBlock
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
    stroke_inferred: bool = False


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


def _contrast_ratio(l1: float, l2: float) -> float:
    higher = max(l1, l2)
    lower = min(l1, l2)
    return (higher + 0.05) / (lower + 0.05)


def _infer_stroke_from_background(
    fill_rgb: Optional[ColorTuple],
    background_rgb: Optional[ColorTuple],
) -> Optional[ColorTuple]:
    if fill_rgb is None:
        return None

    candidates: Sequence[ColorTuple]
    if background_rgb is not None:
        candidates = ((0, 0, 0), (255, 255, 255))
    else:
        fill_lum = relative_luminance(fill_rgb)
        return (0, 0, 0) if fill_lum > 0.5 else (255, 255, 255)

    fill_lum = relative_luminance(fill_rgb)
    bg_lum = relative_luminance(background_rgb) if background_rgb is not None else None

    best: Optional[ColorTuple] = None
    best_score = -1.0
    for candidate in candidates:
        cand_lum = relative_luminance(candidate)
        contrast_with_fill = _contrast_ratio(fill_lum, cand_lum)
        if bg_lum is not None:
            contrast_with_bg = _contrast_ratio(bg_lum, cand_lum)
            score = min(contrast_with_fill, contrast_with_bg)
        else:
            score = contrast_with_fill
        if score > best_score:
            best = candidate
            best_score = score

    return best


def _choose_text_mask(gray: np.ndarray, polygon_mask: np.ndarray) -> np.ndarray:
    interior_pixels = gray[polygon_mask]
    if interior_pixels.size == 0:
        return np.zeros_like(gray, dtype=bool)

    threshold = _auto_threshold(interior_pixels)
    darker = np.logical_and(gray < threshold, polygon_mask)
    lighter = np.logical_and(gray > threshold, polygon_mask)

    dark_count = int(darker.sum())
    light_count = int(lighter.sum())

    def percentile_alternatives() -> list[np.ndarray]:
        if not interior_pixels.size:
            return []
        low_thresh = np.percentile(interior_pixels, 15)
        high_thresh = np.percentile(interior_pixels, 85)
        alt_darker = np.logical_and(gray <= low_thresh, polygon_mask)
        alt_lighter = np.logical_and(gray >= high_thresh, polygon_mask)
        return [alt for alt in (alt_darker, alt_lighter) if alt.any()]

    def pick_best_alternative(alts: Sequence[np.ndarray]) -> Optional[np.ndarray]:
        scored = []
        for alt in alts:
            count = int(alt.sum())
            if count == 0:
                continue
            mean_val = float(np.mean(gray[alt]))
            diff = abs(mean_val - threshold)
            scored.append((diff, count, alt))
        if not scored:
            return None
        scored.sort(key=lambda item: (item[0], item[1]))
        return scored[0][2]

    candidate: Optional[np.ndarray] = None
    other: Optional[np.ndarray] = None

    # Prefer the mask with fewer pixels – glyphs usually occupy the minority of
    # the polygon – but ensure we still return something sensible if the
    # heuristic fails (e.g. extremely small crops or noisy backgrounds).
    if dark_count and light_count:
        if dark_count < light_count:
            candidate = darker
            other = lighter
        else:
            candidate = lighter
            other = darker
        total = dark_count + light_count
        if candidate.sum() > total * 0.7 and other is not None:
            candidate = other
    elif dark_count:
        candidate = darker
    elif light_count:
        candidate = lighter
    else:
        candidate = pick_best_alternative(percentile_alternatives())
        if candidate is None:
            return np.zeros_like(gray, dtype=bool)

    if candidate.sum() == 0:
        return candidate

    polygon_pixels = int(polygon_mask.sum())
    if polygon_pixels and candidate.sum() > polygon_pixels * 0.85:
        alternatives = [alt for alt in percentile_alternatives() if alt.sum() < candidate.sum()]
        replacement = pick_best_alternative(alternatives)
        if replacement is not None:
            candidate = replacement

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

    stroke_inferred = False
    if fill_lum is not None and bg_lum is not None:
        fill_bg_contrast = _contrast_ratio(fill_lum, bg_lum)
    else:
        fill_bg_contrast = None

    if stroke_rgb is None and fill_rgb is not None:
        if fill_bg_contrast is None or fill_bg_contrast < 3.0:
            inferred = _infer_stroke_from_background(fill_rgb, bg_rgb)
            if inferred is not None:
                stroke_rgb = inferred
                stroke_lum = relative_luminance(stroke_rgb)
                stroke_inferred = True
    elif stroke_rgb is not None:
        if bg_rgb is not None:
            bg_distance = np.linalg.norm(np.array(stroke_rgb) - np.array(bg_rgb))
            if bg_distance < 12:
                stroke_rgb = None
                stroke_lum = None
        if stroke_rgb is not None and fill_rgb is not None:
            distance = np.linalg.norm(np.array(stroke_rgb) - np.array(fill_rgb))
            if distance < 18 and bg_rgb is not None:
                inferred = _infer_stroke_from_background(fill_rgb, bg_rgb)
                if inferred is not None:
                    stroke_rgb = inferred
                    stroke_lum = relative_luminance(stroke_rgb)
                    stroke_inferred = True

    if stroke_rgb is None and fill_rgb is not None:
        if fill_bg_contrast is None or fill_bg_contrast < 3.0:
            inferred = _infer_stroke_from_background(fill_rgb, bg_rgb)
            if inferred is not None:
                stroke_rgb = inferred
                stroke_lum = relative_luminance(stroke_rgb)
                stroke_inferred = True

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
        stroke_inferred=stroke_inferred,
    )


def _block_polygon(block: TextBlock) -> Optional[np.ndarray]:
    """Return a polygon suitable for colour analysis for a block."""

    pts = getattr(block, "segm_pts", None)
    if pts is not None:
        try:
            arr = np.asarray(pts, dtype=np.float32).reshape(-1, 2)
            if arr.size >= 6:
                return arr
        except Exception:
            pass

    bbox = getattr(block, "xyxy", None)
    if bbox is None or len(bbox) != 4:
        return None

    x1, y1, x2, y2 = bbox
    return np.array(
        [[float(x1), float(y1)], [float(x2), float(y1)], [float(x2), float(y2)], [float(x1), float(y2)]],
        dtype=np.float32,
    )


def analyse_block_colors(
    image: np.ndarray,
    block: TextBlock,
    ring_radius: int = 6,
    min_core_pixels: int = 50,
) -> Optional[ColorAnalysis]:
    """Analyse the colours of an individual :class:`TextBlock`."""

    if block is None:
        return None

    bbox = getattr(block, "xyxy", None)
    if bbox is None or len(bbox) != 4:
        return None

    try:
        x1, y1, x2, y2 = (int(round(v)) for v in bbox)
    except Exception:
        return None

    if x2 <= x1 or y2 <= y1:
        return None

    polygon = _block_polygon(block)
    if polygon is None or polygon.size < 6:
        return None

    group = TextGroup(blocks=[block], polygon=polygon, bbox=(x1, y1, x2, y2))
    return analyse_group_colors(
        image,
        group,
        ring_radius=ring_radius,
        min_core_pixels=min_core_pixels,
    )


__all__ = ["ColorAnalysis", "analyse_group_colors", "analyse_block_colors"]
