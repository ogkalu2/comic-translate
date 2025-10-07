import numpy as np

from modules.rendering.adaptive_color import (
    TextColorClassifier,
    sample_block_background,
)
from modules.utils.textblock import TextBlock


def _make_block(x1, y1, x2, y2, segm_pts=None):
    return TextBlock(
        text_bbox=np.array([x1, y1, x2, y2], dtype=np.int32),
        text_segm_points=segm_pts,
    )


def _hex_to_rgb(hex_color: str) -> np.ndarray:
    hex_color = hex_color.lstrip("#")
    return np.array([int(hex_color[i : i + 2], 16) for i in (0, 2, 4)], dtype=np.float32) / 255.0


def _relative_luminance(rgb: np.ndarray) -> float:
    return float(0.2126 * rgb[0] + 0.7152 * rgb[1] + 0.0722 * rgb[2])


def test_classifier_prefers_light_text_on_dark_background():
    classifier = TextColorClassifier()
    dark_patch = np.zeros((20, 20, 3), dtype=np.uint8)
    decision = classifier.decide(dark_patch)

    assert decision is not None
    text_rgb = _hex_to_rgb(decision.text_hex)
    outline_rgb = _hex_to_rgb(decision.outline_hex)
    assert _relative_luminance(text_rgb) > 0.55
    assert _relative_luminance(outline_rgb) < 0.15
    assert decision.contrast_ratio >= 4.5


def test_classifier_prefers_dark_text_on_light_background():
    classifier = TextColorClassifier()
    light_patch = np.full((20, 20, 3), 245, dtype=np.uint8)
    decision = classifier.decide(light_patch)

    assert decision is not None
    text_rgb = _hex_to_rgb(decision.text_hex)
    outline_rgb = _hex_to_rgb(decision.outline_hex)
    assert _relative_luminance(text_rgb) < 0.45
    assert _relative_luminance(outline_rgb) > 0.75
    assert decision.contrast_ratio >= 3.5


def test_classifier_ignores_foreground_text_when_background_is_dark():
    classifier = TextColorClassifier()
    bubble = np.full((40, 60, 3), [30, 60, 120], dtype=np.uint8)
    # Simulate bright source text in the centre of the bubble
    bubble[12:28, 15:45] = 235

    decision = classifier.decide(bubble)

    assert decision is not None
    text_rgb = _hex_to_rgb(decision.text_hex)
    outline_rgb = _hex_to_rgb(decision.outline_hex)
    assert _relative_luminance(text_rgb) > _relative_luminance(outline_rgb)
    assert decision.contrast_ratio >= 3.5


def test_classifier_handles_light_background_with_dark_foreground_noise():
    classifier = TextColorClassifier()
    bubble = np.full((40, 60, 3), 235, dtype=np.uint8)
    bubble[10:30, 20:40] = 40

    decision = classifier.decide(bubble)

    assert decision is not None
    text_rgb = _hex_to_rgb(decision.text_hex)
    outline_rgb = _hex_to_rgb(decision.outline_hex)
    assert _relative_luminance(text_rgb) < _relative_luminance(outline_rgb)
    assert decision.contrast_ratio >= 4.0


def test_sample_block_background_fallback_when_shrink_collapses():
    image = np.full((10, 10, 3), 128, dtype=np.uint8)
    blk = _make_block(2, 2, 8, 8)

    patch = sample_block_background(image, blk, shrink_ratio=0.49)

    assert patch is not None
    assert patch.shape[:2] == (6, 6)


def test_sample_block_background_uses_segmentation_bounds():
    image = np.zeros((20, 20, 3), dtype=np.uint8)
    image[5:15, 5:15] = 200
    segm = np.array([[7, 7], [13, 7], [13, 13], [7, 13]], dtype=np.int32)
    blk = _make_block(5, 5, 15, 15, segm_pts=segm)

    patch = sample_block_background(image, blk, shrink_ratio=0.0)

    assert patch is not None
    assert patch.shape[:2] == (6, 6)
    assert np.all(patch == 200)
