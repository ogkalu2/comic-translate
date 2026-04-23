import os
import warnings
from types import SimpleNamespace

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QPointF
from PySide6.QtGui import QColor
from PySide6.QtWidgets import QApplication

from app.controllers.rect_item import RectItemController
from app.controllers.text_scene_item_mixin import TextSceneItemMixin
from app.ui.canvas.text_item import TextBlockItem
from app.ui.canvas.text_item import TextBlockState


def _ensure_app():
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    return app


class _Controller(TextSceneItemMixin):
    def __init__(self):
        self.synced = None
        self.main = SimpleNamespace(
            stage_nav_ctrl=SimpleNamespace(
                calls=[],
                invalidate_for_format_edit=lambda file_path, target_lang: self.main.stage_nav_ctrl.calls.append(
                    ("format", file_path, target_lang)
                ),
                invalidate_for_box_edit=lambda file_path: self.main.stage_nav_ctrl.calls.append(
                    ("box", file_path)
                ),
            ),
            mark_project_dirty=lambda: setattr(self, "dirty", True),
        )

    def _current_file_path(self):
        return "page.png"

    def _current_target_lang(self):
        return "English"

    def _sync_current_render_snapshot(self, file_path=None, *, update_style_overrides=False):
        self.synced = (file_path, update_style_overrides)


def test_text_item_geometry_change_keeps_render_stage():
    ctrl = _Controller()

    ctrl.on_text_item_geometry_changed(None, None)

    assert ctrl.synced == ("page.png", True)
    assert ctrl.main.stage_nav_ctrl.calls == [("format", "page.png", "English")]
    assert ctrl.dirty is True


def test_legacy_rect_change_handler_delegates_text_geometry_to_text_controller():
    calls = []

    class TextCtrl:
        def on_text_item_geometry_changed(self, old_state, new_state):
            calls.append(("text-geometry", old_state, new_state))

    main = SimpleNamespace(
        text_ctrl=TextCtrl(),
        mark_project_dirty=lambda: calls.append(("dirty",)),
    )
    ctrl = RectItemController(main)
    old_state = TextBlockState((0, 0, 10, 10), 0, QPointF(0, 0))
    new_state = TextBlockState((5, 5, 15, 15), 0, QPointF(0, 0))

    ctrl.rect_change_undo(old_state, new_state)

    assert calls == [("text-geometry", old_state, new_state)]


class _SignalConnectController(TextSceneItemMixin):
    def __init__(self):
        self._pending_text_command = None
        self._last_item_text = {}
        self._last_item_html = {}
        self._text_change_timer = SimpleNamespace(stop=lambda: None)
        self.main = SimpleNamespace(
            image_viewer=SimpleNamespace(_bulk_text_restore=False),
            rect_item_ctrl=SimpleNamespace(rect_change_undo=lambda *_args: None),
            curr_tblock_item=None,
        )

    def on_text_item_selected(self, *_args):
        pass

    def on_text_item_deselected(self, *_args):
        pass

    def update_text_block_from_item(self, *_args):
        pass

    def set_values_from_highlight(self, *_args):
        pass


def test_connect_text_item_signals_force_reconnect_does_not_warn():
    _ensure_app()
    ctrl = _SignalConnectController()
    item = TextBlockItem(text="Test", outline_color=QColor("#ffffff"))

    ctrl.connect_text_item_signals(item)

    with warnings.catch_warnings(record=True) as record:
        warnings.simplefilter("always")
        ctrl.connect_text_item_signals(item, force_reconnect=True)

    assert list(record) == []
