"""Utilities for WCAG contrast and luminance calculations."""

from __future__ import annotations

from typing import Iterable, Sequence, Tuple
import numpy as np

ColorLike = Sequence[float]


def _to_linear_rgb(rgb: ColorLike) -> np.ndarray:
    arr = np.asarray(rgb, dtype=np.float32)
    if arr.ndim == 0:
        raise ValueError("RGB colour must be a sequence of length 3")
    if arr.shape[-1] != 3:
        raise ValueError("RGB colour must have exactly three channels")
    if arr.max() > 1.0:
        arr = arr / 255.0
    return np.clip(arr, 0.0, 1.0)


def relative_luminance(rgb: ColorLike) -> float:
    """Compute the WCAG relative luminance of a colour."""

    linear = _to_linear_rgb(rgb)
    coeffs = np.array([0.2126, 0.7152, 0.0722], dtype=np.float32)
    lum = float(np.dot(linear, coeffs))
    return lum


def contrast_ratio(color_a: ColorLike, color_b: ColorLike) -> float:
    """Return the WCAG contrast ratio between two colours."""

    lum1 = relative_luminance(color_a)
    lum2 = relative_luminance(color_b)
    lighter = max(lum1, lum2)
    darker = min(lum1, lum2)
    return (lighter + 0.05) / (darker + 0.05)


def pick_higher_contrast(candidate_a: ColorLike, candidate_b: ColorLike, background: ColorLike) -> Tuple[int, int, int]:
    """Return the candidate with higher contrast against the background."""

    ratio_a = contrast_ratio(candidate_a, background)
    ratio_b = contrast_ratio(candidate_b, background)
    chosen = candidate_a if ratio_a >= ratio_b else candidate_b
    arr = np.asarray(chosen, dtype=np.float32)
    if arr.max() <= 1.0:
        arr = arr * 255.0
    return tuple(int(round(v)) for v in arr)


def ensure_contrast(fill_rgb: ColorLike, background_rgb: ColorLike, target: float = 4.5) -> Tuple[int, int, int]:
    """Return a colour that meets the target contrast against the background."""

    fill = _to_linear_rgb(fill_rgb)
    background = _to_linear_rgb(background_rgb)
    current = contrast_ratio(fill, background)
    if current >= target:
        arr = fill
    else:
        # Snap to whichever extreme (black/white) offers better contrast.
        arr = _to_linear_rgb([0.0, 0.0, 0.0]) if contrast_ratio([0, 0, 0], background) >= contrast_ratio([1, 1, 1], background) else _to_linear_rgb([255, 255, 255])
    return tuple(int(round(v * 255.0)) for v in arr)


def normalize_rgb(rgb: Iterable[float]) -> Tuple[int, int, int]:
    arr = np.asarray(tuple(rgb), dtype=np.float32)
    if arr.max() <= 1.0:
        arr *= 255.0
    arr = np.clip(arr, 0.0, 255.0)
    return tuple(int(round(v)) for v in arr)


__all__ = [
    "contrast_ratio",
    "relative_luminance",
    "ensure_contrast",
    "pick_higher_contrast",
    "normalize_rgb",
]
