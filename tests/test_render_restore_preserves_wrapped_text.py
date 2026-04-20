import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import numpy as np
from PySide6 import QtCore, QtWidgets
from PySide6.QtGui import QColor, QImage, QPainter

from app.ui.canvas.image_viewer import ImageViewer
from app.ui.canvas.save_renderer import ImageSaveRenderer
from app.ui.canvas.text.text_item_properties import TextItemProperties
from app.ui.canvas.text_item import TextBlockItem
from modules.rendering import font_sizing
from modules.rendering import render
from modules.utils.textblock import TextBlock


def _ensure_app():
    app = QtWidgets.QApplication.instance()
    if app is None:
        app = QtWidgets.QApplication([])
    return app


def _make_props():
    return TextItemProperties(
        text="ONE\nTWO",
        source_text="ONE TWO",
        font_family="Arial",
        font_size=20,
        text_color=QColor("#000000"),
        position=(5, 6),
        rotation=0,
        scale=1.0,
        width=80,
        height=40,
        direction=QtCore.Qt.LayoutDirection.LeftToRight,
    )


class _FakeFont:
    def font_variant(self, size):
        return self


class _FakeDraw:
    def multiline_text(self, *args, **kwargs):
        return None


def test_image_viewer_restore_keeps_wrapped_text_after_reflow(monkeypatch):
    _ensure_app()

    def fake_reflow(self, width=None, height=None, max_font_size=None):
        self.font_size = 11
        self.setPlainText("REFLOWED")
        return "REFLOWED", 11

    monkeypatch.setattr(TextBlockItem, "reflow_from_source_text", fake_reflow)

    viewer = ImageViewer(None)
    item = viewer.add_text_item(_make_props())

    assert item.toPlainText() == "ONE\nTWO"
    assert item.font_size == 11


def test_save_renderer_restore_keeps_wrapped_text_after_reflow(monkeypatch):
    _ensure_app()

    def fake_reflow(self, width=None, height=None, max_font_size=None):
        self.font_size = 11
        self.setPlainText("REFLOWED")
        return "REFLOWED", 11

    monkeypatch.setattr(TextBlockItem, "reflow_from_source_text", fake_reflow)

    renderer = ImageSaveRenderer(np.zeros((32, 32, 3), dtype=np.uint8))
    renderer.add_state_to_image({"text_items_state": [_make_props().to_dict()]})

    text_items = [item for item in renderer.scene.items() if isinstance(item, TextBlockItem)]
    assert len(text_items) == 1
    assert text_items[0].toPlainText() == "ONE\nTWO"
    assert text_items[0].font_size == 11


def test_text_block_item_bounding_rect_includes_descender_overflow():
    _ensure_app()

    item = TextBlockItem(
        text="g",
        source_text="g",
        font_family="Arial",
        font_size=40,
        outline_color=None,
    )
    item.set_font("Arial", 40)
    item.set_layout_box_size(40, 40)

    logical_rect = item.get_text_box_rect()
    paint_rect = item.boundingRect()

    assert paint_rect.bottom() > logical_rect.bottom()


def test_text_item_properties_preserve_gradient_and_second_outline():
    props = TextItemProperties(
        text="BOOM",
        text_color=QColor("#111111"),
        second_outline=True,
        second_outline_color=QColor("#222222"),
        second_outline_width=2.5,
        text_gradient=True,
        text_gradient_start_color=QColor("#ff0000"),
        text_gradient_end_color=QColor("#ffff00"),
    )

    restored = TextItemProperties.from_dict(props.to_dict())

    assert restored.second_outline is True
    assert restored.second_outline_color.name() == "#222222"
    assert restored.second_outline_width == 2.5
    assert restored.text_gradient is True
    assert restored.text_gradient_start_color.name() == "#ff0000"
    assert restored.text_gradient_end_color.name() == "#ffff00"


def test_text_block_item_accepts_gradient_and_second_outline():
    _ensure_app()

    item = TextBlockItem(
        text="BOOM",
        text_gradient=True,
        text_gradient_start_color=QColor("#ff0000"),
        text_gradient_end_color=QColor("#ffff00"),
        second_outline=True,
        second_outline_color=QColor("#000000"),
        second_outline_width=2,
    )

    assert item.text_gradient is True
    assert item.second_outline is True
    assert item._paint_overflow_margin() >= 2


def test_text_block_item_paints_selection_bounds_with_gradient():
    _ensure_app()

    item = TextBlockItem(
        text="BOOM",
        text_gradient=True,
        text_gradient_start_color=QColor("#ff0000"),
        text_gradient_end_color=QColor("#ffff00"),
        outline_color=None,
    )
    item.set_layout_box_size(120, 50)
    item.selected = True
    item.setSelected(True)

    image = QImage(180, 100, QImage.Format.Format_ARGB32)
    image.fill(QColor(0, 0, 0, 0))
    painter = QPainter(image)
    item.paint(painter, QtWidgets.QStyleOptionGraphicsItem(), None)
    painter.end()

    assert not image.isNull()


def test_draw_text_uses_pil_target_for_font_size(monkeypatch):
    targets = []

    def fake_resolve(blk, default_max_font_size, min_font_size, target="qt"):
        targets.append(target)
        return 12

    monkeypatch.setattr(render, "resolve_init_font_size", fake_resolve)
    monkeypatch.setattr(
        render,
        "pil_word_wrap",
        lambda image, tbbox_top_left, font_pth, text, roi_width, roi_height, align, spacing, init_font_size, min_font_size=10: (text, init_font_size),
    )
    monkeypatch.setattr(render.ImageFont, "truetype", lambda *args, **kwargs: _FakeFont())
    monkeypatch.setattr(render.ImageDraw, "Draw", lambda image: _FakeDraw())

    image = np.zeros((32, 32, 3), dtype=np.uint8)
    blk = TextBlock(
        text_bbox=np.array([1, 1, 10, 10]),
        translation="AB",
        alignment="left",
        line_spacing=1,
    )

    render.draw_text(image, [blk], "dummy.ttf")

    assert targets == ["pil"]


def test_resolve_init_font_size_supports_distinct_pil_and_qt_units(monkeypatch):
    blk = TextBlock(text_bbox=np.array([1, 1, 10, 10]), font_size_px=24)

    monkeypatch.setattr(font_sizing, "_pixels_to_qfont_points", lambda size_px: size_px / 2)

    assert render.resolve_init_font_size(blk, 40, 10, target="pil") == 24
    assert render.resolve_init_font_size(blk, 40, 10, target="qt") == 12


def test_resolve_init_font_size_handles_missing_max_chars():
    blk = TextBlock(text_bbox=np.array([1, 1, 10, 10]), font_size_px=None)
    blk.max_chars = None

    assert render.resolve_init_font_size(blk, 40, 10, target="pil") == 40
