import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import numpy as np
from PySide6 import QtCore, QtWidgets
from PySide6.QtGui import QColor, QImage, QPainter, QTextCursor

from app.ui.canvas.image_viewer import ImageViewer
from app.ui.canvas.interaction_manager import InteractionManager
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


def _first_char_pixel_size(item):
    cursor = QTextCursor(item.document())
    cursor.setPosition(0)
    cursor.setPosition(1, QTextCursor.MoveMode.KeepAnchor)
    return cursor.charFormat().font().pixelSize()


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


def test_text_block_item_bounding_rect_includes_tall_logical_frame():
    _ensure_app()

    item = TextBlockItem(
        text="short",
        source_text="short",
        font_family="Arial",
        font_size=12,
        outline_color=None,
    )
    item.set_font("Arial", 12)
    item.set_layout_box_size(120, 80)

    logical_rect = item.get_text_box_rect()
    paint_rect = item.boundingRect()

    assert paint_rect.right() >= logical_rect.right()
    assert paint_rect.bottom() >= logical_rect.bottom()


def test_text_block_item_resize_uses_logical_box_not_paint_overflow():
    _ensure_app()

    item = TextBlockItem(
        text="g",
        source_text="g",
        font_family="Arial",
        font_size=40,
        outline_color=QColor("#ffffff"),
        outline_width=8,
    )
    item.set_layout_box_size(40, 40)
    item.init_resize(QtCore.QPointF(0, 0))

    assert item.resize_start_rect == item.get_text_box_rect()
    assert item.resize_start_rect.width() == 40
    assert item.resize_start_rect.height() == 40


def test_text_block_item_resize_hover_matches_logical_bottom_border():
    _ensure_app()

    item = TextBlockItem(
        text="g",
        source_text="g",
        font_family="Arial",
        font_size=40,
        outline_color=QColor("#ffffff"),
        outline_width=8,
    )
    item.set_layout_box_size(40, 40)
    manager = InteractionManager(None)

    assert manager.get_resize_handle(item, QtCore.QPointF(20, 49)) == "bottom"
    assert manager._in_resize_area(item, QtCore.QPointF(20, 49)) is True
    assert manager.get_resize_handle(item, QtCore.QPointF(20, 59)) is None
    assert manager._in_resize_area(item, QtCore.QPointF(20, 59)) is False


def test_text_block_item_resize_from_top_left_normalizes_frame_and_reflows():
    _ensure_app()

    item = TextBlockItem(
        text="This is a long text that must wrap and shrink",
        source_text="This is a long text that must wrap and shrink",
        font_family="Arial",
        font_size=40,
        outline_color=QColor("#ffffff"),
        outline_width=2,
    )
    item.set_layout_box_size(100, 40)
    item.resize_handle = "top_left"
    item.init_resize(QtCore.QPointF(0, 0))

    item.resize_item(QtCore.QPointF(20, 10))

    assert item.pos() == QtCore.QPointF(20, 10)
    assert item.get_text_box_size() == (80.0, 30.0)
    assert item.resize_start_rect == item.get_text_box_rect()
    assert item.document().size().width() <= 80.5
    assert item.document().size().height() <= 30.5


def test_text_block_item_resize_width_keeps_frame_height_and_shrinks_font():
    _ensure_app()

    item = TextBlockItem(
        text="This is a long text that must wrap and shrink",
        source_text="This is a long text that must wrap and shrink",
        font_family="Arial",
        font_size=40,
        outline_color=QColor("#ffffff"),
        outline_width=2,
    )
    item.set_layout_box_size(100, 40)
    item.resize_handle = "right"
    item.init_resize(QtCore.QPointF(100, 20))

    item.resize_item(QtCore.QPointF(60, 20))

    assert item.pos() == QtCore.QPointF(0, 0)
    assert item.get_text_box_size() == (60.0, 40.0)
    assert item.font_size < 40
    assert _first_char_pixel_size(item) == int(round(item.font_size))
    assert item.document().size().height() <= 40.5
    assert item.boundingRect().bottom() >= item.get_text_box_rect().bottom()


def test_text_block_item_resize_width_can_grow_fitted_font():
    _ensure_app()

    text = "This is a long text that must wrap and shrink"
    item = TextBlockItem(
        text=text,
        source_text=text,
        font_family="Arial",
        font_size=10,
        outline_color=QColor("#ffffff"),
        outline_width=2,
    )
    item.set_layout_box_size(60, 40)
    item.reflow_from_source_text(60, 40, max_font_size=10)
    initial_font_size = item.font_size
    item.resize_handle = "right"
    item.init_resize(QtCore.QPointF(60, 20))

    item.resize_item(QtCore.QPointF(160, 20))

    assert item.get_text_box_size() == (160.0, 40.0)
    assert item.font_size > initial_font_size
    assert _first_char_pixel_size(item) == int(round(item.font_size))
    assert item.document().size().height() <= 40.5


def test_image_viewer_add_text_item_applies_fitted_font_size_to_document():
    _ensure_app()

    viewer = ImageViewer(None)
    text = "This is a long text that must wrap and shrink"
    item = viewer.add_text_item(
        TextItemProperties(
            text=text,
            source_text=text,
            font_family="Arial",
            font_size=40,
            text_color=QColor("#000000"),
            outline_color=QColor("#ffffff"),
            outline_width=2,
            width=60,
            height=40,
        )
    )

    assert item.font_size < 40
    assert _first_char_pixel_size(item) == int(round(item.font_size))
    assert item.document().size().height() <= 40.5


def test_text_block_item_set_font_size_uses_pixels():
    _ensure_app()

    item = TextBlockItem(
        text="BOOM",
        source_text="BOOM",
        font_family="Arial",
        font_size=20,
        outline_color=None,
    )

    item.set_font_size(9)

    assert item.font_size == 9
    assert _first_char_pixel_size(item) == 9


def test_text_block_item_plain_text_preserves_layout_width():
    _ensure_app()

    item = TextBlockItem(
        text="short",
        source_text="short",
        font_family="Arial",
        font_size=20,
        outline_color=None,
    )
    item.set_layout_box_size(80, 40)

    item.set_plain_text(
        "This is a much longer string",
        preserve_source_text=True,
        update_width=False,
    )

    assert item.textWidth() == 80
    assert item.get_text_box_size() == (80.0, 40.0)


def test_text_block_item_paint_suppresses_default_selection_frame():
    _ensure_app()

    item = TextBlockItem(text="BOOM", outline_color=None)
    option = QtWidgets.QStyleOptionGraphicsItem()
    option.state |= QtWidgets.QStyle.StateFlag.State_Selected

    paint_option = item._paint_option_without_item_selection(option)

    assert option.state & QtWidgets.QStyle.StateFlag.State_Selected
    assert not (paint_option.state & QtWidgets.QStyle.StateFlag.State_Selected)


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
