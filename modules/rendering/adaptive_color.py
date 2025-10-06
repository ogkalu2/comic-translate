"""Utilities for choosing legible text/outline colours from bubble backgrounds."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional, Tuple

import numpy as np
from numpy.lib.stride_tricks import sliding_window_view

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
        background_lum = stats.get("background_luminance", median_lum)
        alt_cluster = stats.get("secondary_luminance", 1.0 - background_lum)

        # Blend dominant luminance with the median so that extreme sampling
        # artefacts (for example, residual lettering) do not entirely override
        # the underlying bubble tone.
        reference_lum = 0.5 * background_lum + 0.5 * median_lum

        contrast_white = contrast_ratio(reference_lum, 1.0)
        contrast_black = contrast_ratio(reference_lum, 0.0)

        if contrast_white == contrast_black == 0:
            return None

        preferred = None
        if background_lum <= 0.42:
            preferred = "light"
        elif background_lum >= 0.58:
            preferred = "dark"

        forced_choice = preferred is not None

        if preferred == "light":
            text_hex = "#FFFFFF"
            text_lum = 1.0
            probability_light = 0.75
            contrast = contrast_white
        elif preferred == "dark":
            text_hex = "#000000"
            text_lum = 0.0
            probability_light = 0.25
            contrast = contrast_black
        elif contrast_white > contrast_black:
            text_hex = "#FFFFFF"
            text_lum = 1.0
            probability_light = 0.5 + 0.5 * _soft_probability(contrast_white, contrast_black)
            contrast = contrast_white
        else:
            text_hex = "#000000"
            text_lum = 0.0
            probability_light = 0.5 - 0.5 * _soft_probability(contrast_black, contrast_white)
            contrast = contrast_black

        # When both options are below the WCAG target, bias towards the
        # alternative colour if it closes the gap even slightly.
        if contrast < self.min_contrast and not forced_choice:
            alt_hex = "#000000" if text_hex == "#FFFFFF" else "#FFFFFF"
            alt_lum = 0.0 if text_lum == 1.0 else 1.0
            alt_contrast = contrast_ratio(reference_lum, alt_lum)
            if alt_contrast > contrast:
                text_hex = alt_hex
                text_lum = alt_lum
                probability_light = 1.0 - probability_light
                contrast = alt_contrast

        # Prefer an outline that contrasts with both the chosen text colour and
        # the predicted foreground cluster (which often corresponds to the
        # original lettering colour remaining in the patch).
        if abs(alt_cluster - background_lum) < 0.08:
            outline_hex = "#000000" if text_hex == "#FFFFFF" else "#FFFFFF"
        elif alt_cluster >= 0.5:
            outline_hex = "#000000"
        else:
            outline_hex = "#FFFFFF"

        if outline_hex.lower() == text_hex.lower():
            outline_hex = "#FFFFFF" if text_hex == "#000000" else "#000000"

        return AdaptiveColorDecision(
            text_hex=text_hex,
            outline_hex=outline_hex,
            probability_light=probability_light,
            contrast_ratio=contrast,
            background_luminance=background_lum,
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

    smooth_values, _ = _separate_background_and_foreground(luminance)

    if smooth_values.size == 0:
        smooth_values = luminance.reshape(-1)

    trimmed = _trim_extremes(smooth_values)
    mean_l = float(np.mean(trimmed)) if trimmed.size else float(np.mean(smooth_values))
    median_l = float(np.median(trimmed)) if trimmed.size else float(np.median(smooth_values))
    dominant, secondary = _dominant_components(trimmed if trimmed.size else smooth_values)

    return {
        "mean_luminance": mean_l,
        "median_luminance": median_l,
        "background_luminance": float(dominant),
        "secondary_luminance": float(secondary if not np.isnan(secondary) else dominant),
    }


def _soft_probability(primary: float, secondary: float) -> float:
    """Convert contrast differences to a soft confidence score."""

    denom = max(primary + secondary, 1e-6)
    score = (primary - secondary) / denom
    return float(max(0.0, min(1.0, score)))


def _trim_extremes(values: np.ndarray, lower: float = 0.05, upper: float = 0.95) -> np.ndarray:
    if values.size == 0:
        return values

    sorted_vals = np.sort(values.reshape(-1))
    if sorted_vals.size < 5:
        return sorted_vals

    low_idx = int(sorted_vals.size * lower)
    high_idx = int(sorted_vals.size * upper)
    if high_idx <= low_idx:
        return sorted_vals

    return sorted_vals[low_idx:high_idx]


def _median_filter(array: np.ndarray, size: int = 5) -> np.ndarray:
    if array.ndim != 2:
        raise ValueError("Median filter expects a 2D array")

    height, width = array.shape
    eff_size = min(size, height, width)
    if eff_size < 1:
        return array.copy()
    if eff_size % 2 == 0:
        eff_size = max(1, eff_size - 1)
    if eff_size <= 1:
        return array.copy()

    pad = eff_size // 2
    padded = np.pad(array, pad_width=pad, mode="edge")
    windows = sliding_window_view(padded, (eff_size, eff_size))
    return np.median(windows, axis=(-2, -1))


def _separate_background_and_foreground(luminance: np.ndarray) -> Tuple[np.ndarray, np.ndarray]:
    """Return likely background values and the remaining luminance samples."""

    flattened = luminance.reshape(-1)
    if flattened.size == 0:
        return flattened, flattened

    try:
        median_map = _median_filter(luminance, size=5)
    except ValueError:
        median_map = np.full_like(luminance, np.median(flattened))

    diff = np.abs(luminance - median_map)
    diff_flat = diff.reshape(-1)

    grad_y, grad_x = np.gradient(luminance)
    gradient = np.hypot(grad_x, grad_y)
    gradient_flat = gradient.reshape(-1)

    background_mask = None
    if diff_flat.size:
        thresh = np.percentile(diff_flat, 55)
        background_mask = diff_flat <= thresh

    gradient_mask = None
    if gradient_flat.size:
        grad_thresh = np.percentile(gradient_flat, 60)
        gradient_mask = gradient_flat <= grad_thresh

    if background_mask is None and gradient_mask is None:
        return flattened, flattened

    if background_mask is None:
        mask = gradient_mask
    elif gradient_mask is None:
        mask = background_mask
    else:
        mask = background_mask & gradient_mask

    if not np.any(mask):
        # Fall back to the more permissive mask if the intersection removes
        # everything (common for very small patches).
        mask = background_mask if np.any(background_mask) else gradient_mask

    if mask is None or not np.any(mask):
        return flattened, flattened

    background_values = flattened[mask]
    foreground_values = flattened[~mask] if np.any(~mask) else background_values
    return background_values, foreground_values


def _dominant_components(values: np.ndarray) -> Tuple[float, float]:
    if values.size == 0:
        return 0.0, 0.0

    flattened = values.reshape(-1).astype(np.float32)
    if flattened.size > 4096:
        rng = np.random.default_rng(seed=42)
        flattened = rng.choice(flattened, size=4096, replace=False)

    min_val = float(flattened.min())
    max_val = float(flattened.max())
    if np.isclose(min_val, max_val, atol=1e-3):
        return min_val, max_val

    centers = np.array([min_val, max_val], dtype=np.float32)
    labels = np.zeros_like(flattened, dtype=np.int32)

    for _ in range(8):
        distances = np.abs(flattened[:, None] - centers[None, :])
        new_labels = np.argmin(distances, axis=1)
        if np.array_equal(new_labels, labels):
            break
        labels = new_labels
        for idx in range(2):
            members = flattened[labels == idx]
            if members.size:
                centers[idx] = float(np.mean(members))

    counts = np.array([(labels == idx).sum() for idx in range(2)])
    if counts.sum() == 0:
        return float(centers[0]), float(centers[1])

    dominant_idx = int(np.argmax(counts))
    secondary_idx = 1 - dominant_idx

    dominant = float(centers[dominant_idx])
    secondary = float(centers[secondary_idx]) if counts[secondary_idx] else dominant
    return dominant, secondary


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
        original_patch = patch
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
                trimmed_patch = patch[sy1:sy2, sx1:sx2]
                if trimmed_patch.shape[0] >= 3 and trimmed_patch.shape[1] >= 3:
                    patch = trimmed_patch
                else:
                    patch = original_patch

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

