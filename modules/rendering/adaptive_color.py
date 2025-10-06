"""Adaptive text colour selection powered by a lightweight logistic model."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Optional, Tuple

import numpy as np

from ..utils.textblock import TextBlock


@dataclass
class AdaptiveColorDecision:
    """Result of the adaptive colour classifier."""

    text_hex: str
    outline_hex: str
    probability_light: float
    contrast_ratio: float
    background_luminance: float


def _default_model_path() -> Path:
    return Path(__file__).resolve().parents[2] / "resources" / "models" / "text_color_classifier.json"


class TextColorClassifier:
    """Predicts whether light or dark text should be used on a patch."""

    def __init__(self, model_path: Optional[Path] = None):
        self.model_path = Path(model_path) if model_path else _default_model_path()
        self._load_model()

    def _load_model(self):
        if not self.model_path.exists():
            raise FileNotFoundError(
                f"Adaptive text colour model not found at {self.model_path}. "
                "Run tools/train_text_color_model.py to generate it."
            )

        with self.model_path.open("r", encoding="utf-8") as fh:
            payload = json.load(fh)

        self.feature_mean = np.asarray(payload["feature_mean"], dtype=np.float32)
        self.feature_std = np.asarray(payload["feature_std"], dtype=np.float32)
        # Guard against zero variance features
        self.feature_std = np.where(self.feature_std < 1e-6, 1.0, self.feature_std)
        self.weights = np.asarray(payload["weights"], dtype=np.float32)
        self.bias = float(payload["bias"])
        self.feature_names = payload.get("feature_names", [])

    @staticmethod
    def _sigmoid(x: np.ndarray) -> np.ndarray:
        return 1.0 / (1.0 + np.exp(-x))

    def predict_probability(self, features: np.ndarray) -> float:
        """Return probability of using light text for the provided features."""

        if features.shape[0] != self.feature_mean.shape[0]:
            raise ValueError(
                f"Expected {self.feature_mean.shape[0]} features, received {features.shape[0]}"
            )

        normalised = (features - self.feature_mean) / self.feature_std
        score = float(np.dot(self.weights, normalised) + self.bias)
        return float(self._sigmoid(score))

    def decide(self, patch: np.ndarray) -> Optional[AdaptiveColorDecision]:
        """Analyse a patch and return the most legible text/outline colours."""

        if patch is None or patch.size == 0:
            return None

        features, stats = extract_patch_features(patch)
        if features is None:
            return None

        probability_light = self.predict_probability(features)
        background_lum = stats["mean_luminance"]

        text_hex = "#FFFFFF" if probability_light >= 0.5 else "#000000"
        text_lum = 1.0 if text_hex == "#FFFFFF" else 0.0
        contrast = contrast_ratio(background_lum, text_lum)

        # Fallback to the alternate colour when contrast is insufficient.
        alternate_hex = "#000000" if text_hex == "#FFFFFF" else "#FFFFFF"
        alternate_lum = 0.0 if text_hex == "#FFFFFF" else 1.0
        alternate_contrast = contrast_ratio(background_lum, alternate_lum)

        if contrast < 4.5 and alternate_contrast > contrast:
            text_hex = alternate_hex
            text_lum = alternate_lum
            contrast = alternate_contrast
            probability_light = 1.0 - probability_light

        outline_hex = "#000000" if text_hex == "#FFFFFF" else "#FFFFFF"

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


def extract_patch_features(patch: np.ndarray) -> Tuple[Optional[np.ndarray], dict]:
    """Extract luminance and texture features from an RGB patch."""

    if patch is None or patch.size == 0:
        return None, {}

    patch_float = patch.astype(np.float32) / 255.0

    luminance = (
        0.2126 * patch_float[..., 0]
        + 0.7152 * patch_float[..., 1]
        + 0.0722 * patch_float[..., 2]
    )

    mean_l = float(np.mean(luminance))
    std_l = float(np.std(luminance))
    min_l = float(np.min(luminance))
    max_l = float(np.max(luminance))
    range_l = max_l - min_l

    # HSV conversion for saturation/value estimation
    maxc = np.max(patch_float, axis=2)
    minc = np.min(patch_float, axis=2)
    delta = maxc - minc
    saturation = np.where(maxc > 0, delta / np.maximum(maxc, 1e-6), 0.0)
    mean_s = float(np.mean(saturation))
    mean_v = float(np.mean(maxc))

    gy, gx = np.gradient(luminance)
    grad = np.sqrt(gx ** 2 + gy ** 2)
    edge_strength = float(np.mean(grad))

    features = np.array(
        [mean_l, std_l, range_l, mean_s, mean_v, edge_strength], dtype=np.float32
    )
    stats = {
        "mean_luminance": mean_l,
    }

    return features, stats


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

