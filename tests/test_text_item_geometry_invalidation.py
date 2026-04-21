from types import SimpleNamespace

from PySide6.QtCore import QPointF

from app.controllers.rect_item import RectItemController
from app.controllers.text_scene_item_mixin import TextSceneItemMixin
from app.ui.canvas.text_item import TextBlockState


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
