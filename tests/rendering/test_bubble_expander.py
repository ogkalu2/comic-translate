import pytest
import numpy as np
from modules.rendering.bubble_expander import BubbleDetector, BubbleExpander, ArtStyleProfile

def _white_circle_image(size=200, radius=80):
    img = np.zeros((size, size, 3), dtype=np.uint8)
    cx, cy = size // 2, size // 2
    for y in range(size):
        for x in range(size):
            if (x - cx)**2 + (y - cy)**2 < radius**2:
                img[y, x] = 255
    return img

def test_bubble_detected_in_circle_image():
    img = _white_circle_image()
    detector = BubbleDetector()
    masks = detector.detect(img)
    assert len(masks) >= 1

def test_no_bubble_in_blank_image():
    img = np.zeros((200, 200, 3), dtype=np.uint8)
    detector = BubbleDetector()
    masks = detector.detect(img)
    assert len(masks) == 0

def test_expander_clips_to_bubble_mask():
    from modules.rendering.collision_resolver import RenderBox
    img = _white_circle_image(size=200, radius=80)
    detector = BubbleDetector()
    masks = detector.detect(img)
    assert masks

    box = RenderBox(id="a", x=80, y=80, width=40, height=40,
                    translated_text="hello", font_size=12.0)
    expander = BubbleExpander()
    expanded = expander.expand(box, masks[0], max_expand_px=30)
    assert expanded.x >= 0
    assert expanded.y >= 0
    assert expanded.x + expanded.width <= 200
    assert expanded.y + expanded.height <= 200

def test_art_style_profile_clean_digital():
    p = ArtStyleProfile.clean_digital()
    assert p.min_solidity >= 0.85
