"""Colour sampling routines for Torii-style auto rendering."""

from __future__ import annotations

import colorsys
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


def _adjust_lightness(rgb: ColorTuple, factor: float, lighten: bool) -> ColorTuple:
    r, g, b = (c / 255.0 for c in rgb)
    h, l, s = colorsys.rgb_to_hls(r, g, b)
    if lighten:
        new_l = min(1.0, l + (1.0 - l) * factor)
    else:
        new_l = max(0.0, l * (1.0 - factor))
    nr, ng, nb = colorsys.hls_to_rgb(h, new_l, s)
    return (int(round(nr * 255.0)), int(round(ng * 255.0)), int(round(nb * 255.0)))


def _background_outline_candidates(background_rgb: Optional[ColorTuple]) -> Tuple[ColorTuple, ...]:
    if background_rgb is None:
        return tuple()

    base = tuple(int(max(0, min(255, v))) for v in background_rgb)
    variants = {base}
    # Generate a gradient of progressively darker tones that keep the same hue.
    for factor in (0.1, 0.18, 0.28, 0.4, 0.55, 0.7, 0.85):
        variants.add(_adjust_lightness(base, factor, lighten=False))
    return tuple(variants)


def _infer_stroke_from_background(
    fill_rgb: Optional[ColorTuple],
    background_rgb: Optional[ColorTuple],
) -> Optional[ColorTuple]:
    if fill_rgb is None:
        return None

    fill_arr = np.array(fill_rgb, dtype=np.float32)
    bg_arr = np.array(background_rgb, dtype=np.float32) if background_rgb is not None else None

    fill_lum = relative_luminance(fill_rgb)
    bg_lum = relative_luminance(background_rgb) if background_rgb is not None else None

    bg_candidates = _background_outline_candidates(background_rgb)
    preferred: Optional[ColorTuple] = None
    darker_candidates: list[Tuple[float, ColorTuple]] = []
    relaxed_candidates: list[Tuple[float, ColorTuple]] = []
    for candidate in bg_candidates:
        if background_rgb is not None and candidate == background_rgb:
            continue
        cand_arr = np.array(candidate, dtype=np.float32)
        cand_lum = relative_luminance(candidate)
        contrast_with_fill = _contrast_ratio(fill_lum, cand_lum)
        contrast_with_bg = _contrast_ratio(bg_lum, cand_lum) if bg_lum is not None else None

        if contrast_with_fill < 2.3:
            continue

        if bg_lum is not None and cand_lum >= bg_lum:
            continue

        if bg_lum is not None and bg_lum > 0.25 and cand_lum < bg_lum * 0.2:
            continue

        if contrast_with_bg is not None and contrast_with_bg < 1.2:
            continue

        distance_to_fill = np.linalg.norm(cand_arr - fill_arr)
        if distance_to_fill < 18:
            continue

        distance_to_bg = np.linalg.norm(cand_arr - bg_arr) if bg_arr is not None else 0.0
        colour_similarity = max(0.0, 1.0 - distance_to_bg / 220.0)
        darkness_delta = (bg_lum - cand_lum) if bg_lum is not None else 0.0
        darkness_bonus = min(max(darkness_delta, 0.0) * 0.8, 0.8)
        base_contrast = min(contrast_with_fill, contrast_with_bg or contrast_with_fill)
        base_contrast = min(base_contrast, 3.0)
        score = base_contrast + darkness_bonus + colour_similarity

        if bg_lum is None or cand_lum <= bg_lum - 0.02:
            darker_candidates.append((score, candidate))
        else:
            relaxed_candidates.append((score, candidate))

    for candidate_list in (darker_candidates, relaxed_candidates):
        for score, candidate in sorted(candidate_list, key=lambda item: item[0], reverse=True):
            preferred = candidate
            break
        if preferred is not None:
            break

    if preferred is None and background_rgb is not None:
        # Try progressively darker variants even if they fail the strict contrast
        # thresholds. This keeps the outline distinct from the text colour while
        # still respecting the background hue.
        for factor in (0.3, 0.45, 0.6, 0.75, 0.9):
            candidate = _adjust_lightness(background_rgb, factor, lighten=False)
            cand_lum = relative_luminance(candidate)
            if bg_lum is not None and cand_lum >= bg_lum:
                continue
            contrast_with_fill = _contrast_ratio(fill_lum, cand_lum)
            if contrast_with_fill < 1.6:
                continue
            distance_to_fill = np.linalg.norm(np.array(candidate, dtype=np.float32) - fill_arr)
            if distance_to_fill < 18:
                continue
            if bg_arr is not None and np.linalg.norm(np.array(candidate, dtype=np.float32) - bg_arr) > 190:
                continue
            preferred = candidate
            break

    if preferred is not None:
        return preferred

    candidates: Sequence[ColorTuple] = ((0, 0, 0), (255, 255, 255))
    best: Optional[ColorTuple] = None
    best_score = -1.0
    for candidate in candidates:
        cand_lum = relative_luminance(candidate)
        contrast_with_fill = _contrast_ratio(fill_lum, cand_lum)
        contrast_with_bg = (
            _contrast_ratio(bg_lum, cand_lum) if bg_lum is not None else contrast_with_fill
        )
        score = min(contrast_with_fill, contrast_with_bg)
        if score > best_score:
            best = candidate
            best_score = score

    if best is not None:
        return best

    if background_rgb is not None:
        return _adjust_lightness(
            background_rgb,
            0.5,
            lighten=relative_luminance(background_rgb) <= 0.5,
        )

    return (0, 0, 0) if fill_lum > 0.5 else (255, 255, 255)


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
            if bg_distance < 12 or (stroke_lum is not None and stroke_lum >= bg_lum - 0.01):
                stroke_rgb = None
                stroke_lum = None
        if stroke_rgb is not None and fill_rgb is not None:
            distance = np.linalg.norm(np.array(stroke_rgb) - np.array(fill_rgb))
            if distance < 24 and bg_rgb is not None:
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
