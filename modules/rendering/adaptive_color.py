"""Utilities for choosing legible text/outline colours from bubble backgrounds."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

import numpy as np

from ..utils.textblock import TextBlock


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


def sample_block_background(
    image: np.ndarray,
    blk: TextBlock,
    shrink_ratio: float = 0.12,
) -> Optional[np.ndarray]:
    """Return an RGB patch representing the speech bubble background."""

    if image is None:
        return None

    h, w = image.shape[:2]
    if getattr(blk, "bubble_xyxy", None) is not None:
        x1, y1, x2, y2 = blk.bubble_xyxy
    else:
        x1, y1, x2, y2 = blk.xyxy

    x1, y1, x2, y2 = int(x1), int(y1), int(x2), int(y2)
    width = max(0, x2 - x1)
    height = max(0, y2 - y1)
    if width <= 2 or height <= 2:
        return None

    dx = int(width * shrink_ratio)
    dy = int(height * shrink_ratio)

    rx1 = max(0, x1 + dx)
    ry1 = max(0, y1 + dy)
    rx2 = min(w, x2 - dx)
    ry2 = min(h, y2 - dy)

    if rx2 <= rx1 or ry2 <= ry1:
        return None

    patch = image[ry1:ry2, rx1:rx2]
    if patch.size == 0:
        return None

    return patch


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

