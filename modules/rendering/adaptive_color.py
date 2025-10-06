"""Utilities for choosing legible text/outline colours from bubble backgrounds."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

import numpy as np

from ..utils.textblock import TextBlock
from ..detection.utils.bubbles import make_bubble_mask, bubble_interior_bounds


@dataclass
class AdaptiveColorDecision:
    """Result of the adaptive colour heuristic."""

    text_hex: str
    outline_hex: str
    probability_light: float
    contrast_ratio: float
    background_luminance: float


class TextColorClassifier:
    """Contrast-ratio based selector for bubble-safe colours.

    The implementation favours white or black text depending on which colour
    provides the stronger WCAG contrast ratio against the sampled bubble
    interior.  This approach mirrors the behaviour demonstrated in many
    professionally lettered webtoons while avoiding the brittleness of a
    learned model.
    """

    def __init__(self, min_contrast: float = 4.5):
        self.min_contrast = float(min_contrast)

    def decide(self, patch: np.ndarray) -> Optional[AdaptiveColorDecision]:
        """Analyse a patch and return the most legible text/outline colours."""

        if patch is None or patch.size == 0:
            return None

        stats = extract_patch_statistics(patch)
        if not stats:
            return None

        mean_lum = stats["mean_luminance"]
        median_lum = stats["median_luminance"]
        reference_lum = 0.6 * median_lum + 0.4 * mean_lum

        contrast_white = contrast_ratio(reference_lum, 1.0)
        contrast_black = contrast_ratio(reference_lum, 0.0)

        if contrast_white == contrast_black == 0:
            return None

        if contrast_white > contrast_black:
            text_hex = "#FFFFFF"
            text_lum = 1.0
            probability_light = 1.0
            contrast = contrast_white
        else:
            text_hex = "#000000"
            text_lum = 0.0
            probability_light = 0.0
            contrast = contrast_black

        # When both options are below the WCAG target, bias towards the
        # alternative colour if it closes the gap even slightly.
        if contrast < self.min_contrast:
            alt_hex = "#000000" if text_hex == "#FFFFFF" else "#FFFFFF"
            alt_lum = 0.0 if text_lum == 1.0 else 1.0
            alt_contrast = contrast_ratio(reference_lum, alt_lum)
            if alt_contrast > contrast:
                text_hex = alt_hex
                text_lum = alt_lum
                probability_light = 1.0 - probability_light
                contrast = alt_contrast

        outline_hex = "#000000" if text_hex == "#FFFFFF" else "#FFFFFF"

        return AdaptiveColorDecision(
            text_hex=text_hex,
            outline_hex=outline_hex,
            probability_light=probability_light,
            contrast_ratio=contrast,
            background_luminance=mean_lum,
        )


def contrast_ratio(background_lum: float, text_lum: float) -> float:
    """Compute WCAG contrast ratio between two luminance levels."""

    l1, l2 = max(background_lum, text_lum), min(background_lum, text_lum)
    return (l1 + 0.05) / (l2 + 0.05)


def extract_patch_statistics(patch: np.ndarray) -> dict:
    """Compute luminance statistics that drive the contrast heuristic."""

    if patch is None or patch.size == 0:
        return {}

    if patch.ndim == 2:
        patch = np.stack([patch] * 3, axis=-1)
    elif patch.ndim == 3 and patch.shape[2] >= 4:
        patch = patch[..., :3]

    patch_float = patch.astype(np.float32) / 255.0

    luminance = (
        0.2126 * patch_float[..., 0]
        + 0.7152 * patch_float[..., 1]
        + 0.0722 * patch_float[..., 2]
    )

    if luminance.size == 0:
        return {}

    # Use trimmed statistics to reduce the influence of outlines or artefacts
    flattened = luminance.reshape(-1)
    trimmed = np.sort(flattened)
    if trimmed.size > 20:
        lower = int(trimmed.size * 0.1)
        upper = int(trimmed.size * 0.9)
        trimmed = trimmed[lower:upper]

    mean_l = float(np.mean(trimmed))
    median_l = float(np.median(trimmed))

    return {
        "mean_luminance": mean_l,
        "median_luminance": median_l,
    }


def _clamp_bounds(
    bounds: tuple[int, int, int, int],
    width: int,
    height: int,
) -> tuple[int, int, int, int]:
    x1, y1, x2, y2 = bounds
    x1 = max(0, min(width, int(round(x1))))
    y1 = max(0, min(height, int(round(y1))))
    x2 = max(x1, min(width, int(round(x2))))
    y2 = max(y1, min(height, int(round(y2))))
    return x1, y1, x2, y2


def _interior_from_segmentation(
    blk: TextBlock,
    bbox: tuple[int, int, int, int],
) -> Optional[tuple[int, int, int, int]]:
    pts = getattr(blk, "segm_pts", None)
    if pts is None or len(pts) == 0:
        return None

    try:
        pts_arr = np.asarray(pts, dtype=np.int32)
        if pts_arr.ndim != 2 or pts_arr.shape[1] != 2:
            return None
    except Exception:
        return None

    x1, y1, x2, y2 = bbox
    local = pts_arr.copy()
    local[:, 0] -= x1
    local[:, 1] -= y1

    min_x = max(0, int(np.min(local[:, 0])))
    min_y = max(0, int(np.min(local[:, 1])))
    max_x = int(np.max(local[:, 0]))
    max_y = int(np.max(local[:, 1]))

    if max_x <= min_x or max_y <= min_y:
        return None

    return (min_x, min_y, max_x, max_y)


def _interior_via_mask(patch: np.ndarray) -> Optional[tuple[int, int, int, int]]:
    try:
        mask = make_bubble_mask(patch)
    except Exception:
        return None

    if mask is None or mask.size == 0:
        return None

    if mask.ndim == 3:
        mask = mask[..., 0]

    interior = bubble_interior_bounds(mask > 0)
    return interior


def sample_block_background(
    image: np.ndarray,
    blk: TextBlock,
    shrink_ratio: float = 0.12,
) -> Optional[np.ndarray]:
    """Return an RGB patch representing the speech bubble background."""

    if image is None:
        return None

    height, width = image.shape[:2]
    if getattr(blk, "bubble_xyxy", None) is not None:
        bbox = tuple(blk.bubble_xyxy)
    else:
        bbox = tuple(blk.xyxy)

    x1, y1, x2, y2 = _clamp_bounds(bbox, width, height)
    region_w = x2 - x1
    region_h = y2 - y1
    if region_w <= 2 or region_h <= 2:
        return None

    patch = image[y1:y2, x1:x2]
    if patch.size == 0:
        return None

    interior = _interior_from_segmentation(blk, (x1, y1, x2, y2))
    if interior is None and getattr(blk, "text_class", "") == "text_bubble":
        interior = _interior_via_mask(patch)

    if interior is not None:
        ix1, iy1, ix2, iy2 = interior
        ix1 = max(0, min(region_w, ix1))
        iy1 = max(0, min(region_h, iy1))
        ix2 = max(ix1 + 1, min(region_w, ix2))
        iy2 = max(iy1 + 1, min(region_h, iy2))
        patch = patch[iy1:iy2, ix1:ix2]

    if patch.size == 0:
        return None

    if shrink_ratio > 0:
        inner_w = patch.shape[1]
        inner_h = patch.shape[0]
        dx = int(inner_w * shrink_ratio)
        dy = int(inner_h * shrink_ratio)
        if dx > 0 or dy > 0:
            sx1 = dx
            sy1 = dy
            sx2 = inner_w - dx
            sy2 = inner_h - dy
            if sx2 > sx1 and sy2 > sy1:
                patch = patch[sy1:sy2, sx1:sx2]

    return patch if patch.size else None


def determine_text_outline_colors(
    image: np.ndarray,
    blk: TextBlock,
    classifier: TextColorClassifier,
    shrink_ratio: float = 0.12,
) -> Optional[AdaptiveColorDecision]:
    """Convenience helper that samples a block and runs the classifier."""

    patch = sample_block_background(image, blk, shrink_ratio=shrink_ratio)
    if patch is None:
        return None

    return classifier.decide(patch)


__all__ = [
    "AdaptiveColorDecision",
    "TextColorClassifier",
    "determine_text_outline_colors",
    "sample_block_background",
    "contrast_ratio",
]

