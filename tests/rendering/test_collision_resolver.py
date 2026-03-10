import pytest
import numpy as np
from modules.rendering.collision_resolver import CollisionResolver, RenderBox

def _box(id, x1, y1, x2, y2, text="hello world foo bar"):
    return RenderBox(id=id, x=x1, y=y1, width=x2-x1, height=y2-y1,
                     translated_text=text, font_size=20.0)

def test_no_collision_unchanged():
    boxes = [_box("a", 0, 0, 100, 50), _box("b", 200, 0, 300, 50)]
    resolver = CollisionResolver()
    result = resolver.resolve(boxes, bubble_masks={})
    assert not any(b.needs_review for b in result)

def test_overlapping_boxes_font_reduced():
    boxes = [_box("a", 0, 0, 100, 50), _box("b", 50, 0, 150, 50)]
    resolver = CollisionResolver()
    result = resolver.resolve(boxes, bubble_masks={})
    reduced = [b for b in result if b.font_size < 20.0]
    assert len(reduced) > 0

def test_anchor_xy_never_changes():
    boxes = [_box("a", 10, 20, 110, 70), _box("b", 60, 20, 160, 70)]
    resolver = CollisionResolver()
    result = resolver.resolve(boxes, bubble_masks={})
    for b in result:
        orig = {"a": (10, 20), "b": (60, 20)}[b.id]
        assert (b.x, b.y) == orig
