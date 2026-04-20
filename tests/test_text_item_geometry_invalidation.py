from types import SimpleNamespace

from app.controllers.text_scene_item_mixin import TextSceneItemMixin


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
