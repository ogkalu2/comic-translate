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

        background_lum = stats.get("background_luminance", stats["median_luminance"])
        background_rgb = stats.get("background_rgb")

        if background_rgb is None:
            return None

        prefer_light = background_lum <= 0.5
        target_rgb = np.ones(3, dtype=np.float32) if prefer_light else np.zeros(3, dtype=np.float32)

        text_rgb, mix = _solve_mix_for_contrast(
            base_rgb=background_rgb,
            reference_lum=background_lum,
            target_rgb=target_rgb,
            min_contrast=self.min_contrast,
        )

        mix_floor = 0.6 if background_lum <= 0.5 else 0.45
        if mix < mix_floor:
            text_rgb = background_rgb * (1.0 - mix_floor) + target_rgb * mix_floor
            mix = mix_floor

        text_lum = _relative_luminance(text_rgb)
        contrast = contrast_ratio(background_lum, text_lum)

        # If contrast is still under the target, fall back to the pure extreme.
        if contrast < self.min_contrast:
            text_rgb = target_rgb
            text_lum = _relative_luminance(text_rgb)
            contrast = contrast_ratio(background_lum, text_lum)

        probability_light = 0.75 if text_lum >= background_lum else 0.25

        outline_target = np.zeros(3, dtype=np.float32) if text_lum >= background_lum else np.ones(3, dtype=np.float32)
        outline_rgb, outline_mix = _solve_mix_for_contrast(
            base_rgb=background_rgb,
            reference_lum=text_lum,
            target_rgb=outline_target,
            min_contrast=max(3.0, self.min_contrast - 1.0),
        )

        outline_floor = 0.35 if text_lum >= background_lum else 0.3
        if outline_mix < outline_floor:
            outline_rgb = background_rgb * (1.0 - outline_floor) + outline_target * outline_floor

        outline_lum = _relative_luminance(outline_rgb)
        outline_contrast = contrast_ratio(text_lum, outline_lum)

        if outline_contrast < 1.5:
            outline_rgb = outline_target
            outline_lum = _relative_luminance(outline_rgb)

        text_hex = _rgb_to_hex(text_rgb)
        outline_hex = _rgb_to_hex(outline_rgb)

        if outline_hex.lower() == text_hex.lower():
            outline_hex = "#000000" if text_lum >= background_lum else "#FFFFFF"

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


def _relative_luminance(rgb: np.ndarray) -> float:
    rgb = np.clip(np.asarray(rgb, dtype=np.float32), 0.0, 1.0)
    return float(0.2126 * rgb[0] + 0.7152 * rgb[1] + 0.0722 * rgb[2])


def _solve_mix_for_contrast(
    base_rgb: np.ndarray,
    reference_lum: float,
    target_rgb: np.ndarray,
    min_contrast: float,
) -> Tuple[np.ndarray, float]:
    """Blend the base colour toward the target until contrast is satisfied."""

    base_rgb = np.clip(np.asarray(base_rgb, dtype=np.float32), 0.0, 1.0)
    target_rgb = np.clip(np.asarray(target_rgb, dtype=np.float32), 0.0, 1.0)

    base_lum = _relative_luminance(base_rgb)
    if contrast_ratio(reference_lum, base_lum) >= min_contrast:
        return base_rgb, 0.0

    low, high = 0.0, 1.0
    best = None
    best_mix = 1.0

    for _ in range(24):
        mid = (low + high) / 2.0
        candidate = base_rgb * (1.0 - mid) + target_rgb * mid
        cand_lum = _relative_luminance(candidate)
        ratio = contrast_ratio(reference_lum, cand_lum)
        if ratio >= min_contrast:
            best = candidate
            best_mix = mid
            high = mid
        else:
            low = mid

    if best is None:
        best = target_rgb
        best_mix = 1.0

    return best, best_mix


def _rgb_to_hex(rgb: np.ndarray) -> str:
    rgb = np.clip(np.asarray(rgb, dtype=np.float32), 0.0, 1.0)
    values = np.round(rgb * 255.0).astype(np.int32)
    return "#" + "".join(f"{val:02X}" for val in values)


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

    smooth_values, _, background_mask = _separate_background_and_foreground(luminance)

    if smooth_values.size == 0:
        smooth_values = luminance.reshape(-1)

    trimmed = _trim_extremes(smooth_values)
    reference_values = trimmed if trimmed.size else smooth_values
    mean_l = float(np.mean(reference_values)) if reference_values.size else float(np.mean(smooth_values))
    median_l = float(np.median(reference_values)) if reference_values.size else float(np.median(smooth_values))
    dominant, secondary = _dominant_components(reference_values if reference_values.size else smooth_values)

    rgb_flat = patch_float.reshape(-1, 3)
    if background_mask is not None and background_mask.size == luminance.size:
        mask_flat = background_mask.reshape(-1)
        background_rgb = rgb_flat[mask_flat]
    else:
        background_rgb = rgb_flat

    if background_rgb.size == 0:
        background_rgb = rgb_flat

    background_rgb = np.mean(background_rgb, axis=0) if background_rgb.size else np.array([0.5, 0.5, 0.5], dtype=np.float32)

    return {
        "mean_luminance": mean_l,
        "median_luminance": median_l,
        "background_luminance": float(dominant),
        "secondary_luminance": float(secondary if not np.isnan(secondary) else dominant),
        "background_rgb": background_rgb.astype(np.float32),
    }


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


def _separate_background_and_foreground(
    luminance: np.ndarray,
) -> Tuple[np.ndarray, np.ndarray, Optional[np.ndarray]]:
    """Return likely background values, foreground values, and a background mask."""

    flattened = luminance.reshape(-1)
    if flattened.size == 0:
        return flattened, flattened, None

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
        return flattened, flattened, None

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
        return flattened, flattened, None

    background_values = flattened[mask]
    foreground_values = flattened[~mask] if np.any(~mask) else background_values
    try:
        mask_full = mask.reshape(luminance.shape)
    except ValueError:
        mask_full = np.broadcast_to(mask, luminance.shape)
    return background_values, foreground_values, mask_full


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

