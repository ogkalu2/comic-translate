"""Utility script to train the adaptive text colour classifier."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Tuple

import numpy as np

from modules.rendering.adaptive_color import (
    contrast_ratio,
    extract_patch_features,
)


ROOT = Path(__file__).resolve().parents[1]
MODEL_DIR = ROOT / "resources" / "models"
MODEL_PATH = MODEL_DIR / "text_color_classifier.json"


def random_patch(size: int = 64) -> np.ndarray:
    """Generate a synthetic bubble background patch."""

    base_color = np.random.rand(3)
    patch = np.ones((size, size, 3), dtype=np.float32)
    patch[:] = base_color

    # Add smooth gradients or lighting variations
    if np.random.rand() < 0.6:
        gradient_axis = np.random.choice([0, 1])
        ramp = np.linspace(0, 1, size, dtype=np.float32)
        if gradient_axis == 0:
            ramp = ramp[:, None, None]
        else:
            ramp = ramp[None, :, None]
        strength = np.random.uniform(-0.3, 0.3)
        patch += strength * ramp

    # Apply chromatic noise to mimic printed textures
    noise_strength = np.random.beta(2, 8) * 0.6
    noise = (np.random.rand(size, size, 3) - 0.5) * noise_strength
    patch += noise

    # Occasionally add a darker or lighter vignette
    if np.random.rand() < 0.35:
        yy, xx = np.meshgrid(np.linspace(-1, 1, size), np.linspace(-1, 1, size), indexing="ij")
        radius = np.sqrt(xx ** 2 + yy ** 2)
        vignette_strength = np.random.uniform(-0.4, 0.4)
        patch += vignette_strength * (1 - radius)[..., None]

    patch = np.clip(patch, 0.0, 1.0)
    return (patch * 255).astype(np.uint8)


def label_patch(mean_luminance: float) -> int:
    """Return 1 if white text has better contrast, else 0."""

    contrast_white = contrast_ratio(mean_luminance, 1.0)
    contrast_black = contrast_ratio(mean_luminance, 0.0)

    if abs(contrast_white - contrast_black) < 0.05:
        return 1 if mean_luminance < 0.5 else 0

    return 1 if contrast_white >= contrast_black else 0


def generate_dataset(samples: int = 6000) -> Tuple[np.ndarray, np.ndarray]:
    feature_vectors = []
    labels = []

    for _ in range(samples):
        patch = random_patch()
        features, stats = extract_patch_features(patch)
        if features is None:
            continue

        lbl = label_patch(stats["mean_luminance"])
        feature_vectors.append(features)
        labels.append(lbl)

    return np.stack(feature_vectors), np.asarray(labels, dtype=np.float32)


def train_logistic_regression(
    features: np.ndarray, labels: np.ndarray, lr: float = 0.1, epochs: int = 2500
) -> Tuple[np.ndarray, float, np.ndarray, np.ndarray]:
    n_samples, n_features = features.shape
    feat_mean = np.mean(features, axis=0)
    feat_std = np.std(features, axis=0)
    feat_std = np.where(feat_std < 1e-6, 1.0, feat_std)

    norm_features = (features - feat_mean) / feat_std

    weights = np.zeros(n_features, dtype=np.float64)
    bias = 0.0

    for epoch in range(epochs):
        logits = norm_features @ weights + bias
        preds = 1.0 / (1.0 + np.exp(-logits))
        error = preds - labels

        grad_w = (norm_features.T @ error) / n_samples
        grad_b = np.mean(error)

        weights -= lr * grad_w
        bias -= lr * grad_b

        if (epoch + 1) % 500 == 0:
            accuracy = np.mean((preds >= 0.5) == labels)
            print(f"Epoch {epoch + 1}/{epochs} - accuracy: {accuracy:.4f}")

    return weights.astype(np.float32), float(bias), feat_mean.astype(np.float32), feat_std.astype(np.float32)


def main():
    np.random.seed(42)
    print("Generating synthetic dataset...")
    features, labels = generate_dataset()
    print(f"Dataset size: {features.shape[0]} samples")

    print("Training logistic regression model...")
    weights, bias, feat_mean, feat_std = train_logistic_regression(features, labels)

    model = {
        "feature_names": [
            "mean_luminance",
            "luminance_std",
            "luminance_range",
            "mean_saturation",
            "mean_value",
            "edge_strength",
        ],
        "feature_mean": feat_mean.tolist(),
        "feature_std": feat_std.tolist(),
        "weights": weights.tolist(),
        "bias": bias,
        "metadata": {
            "samples": int(features.shape[0]),
            "epochs": 2500,
            "learning_rate": 0.1,
        },
    }

    MODEL_DIR.mkdir(parents=True, exist_ok=True)
    with MODEL_PATH.open("w", encoding="utf-8") as fh:
        json.dump(model, fh, indent=2)

    print(f"Model saved to {MODEL_PATH}")


if __name__ == "__main__":
    main()

