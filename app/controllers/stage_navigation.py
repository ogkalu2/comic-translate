from __future__ import annotations

from typing import TYPE_CHECKING

from app.controllers.stage_view_apply_mixin import StageViewApplyMixin
from app.controllers.stage_view_state_mixin import StageViewStateMixin, UI_STAGE_ORDER
from app.ui.dayu_widgets.push_button import MPushButton
from pipeline.invalidation_policy import (
    invalidate_page_for_box_edit,
    invalidate_page_for_format_edit,
    invalidate_page_for_segmentation_edit,
    invalidate_page_for_source_text_edit,
    invalidate_page_for_translated_text_edit,
)
from pipeline.page_state import has_runtime_patches as page_has_runtime_patches
from pipeline.stage_state import is_stage_available, mark_clean_ready

if TYPE_CHECKING:
    from controller import ComicTranslate


BUTTON_STAGE_MAP = {
    0: "text",
    1: "clean",
    2: "render",
}


class StageNavigationController(StageViewApplyMixin, StageViewStateMixin):
    def __init__(self, main: ComicTranslate) -> None:
        self.main = main

    def refresh_stage_buttons(self, file_path: str | None = None) -> None:
        current_file = self._current_file_path()
        if file_path and current_file and file_path != current_file:
            return
        file_path = current_file or file_path
        buttons = self.main.hbutton_group.get_button_group().buttons()
        if not file_path or file_path not in self.main.image_states:
            for button in buttons:
                button.setEnabled(False)
                if hasattr(button, "set_dayu_type"):
                    button.set_dayu_type(MPushButton.DefaultType)
            return

        page_ctx = self._get_page_context(file_path)
        state = page_ctx.state
        target_lang = page_ctx.target_lang
        has_runtime_patches = page_ctx.has_runtime_patches
        current_ui_stage = self.get_ui_stage(file_path)

        for idx, button in enumerate(buttons):
            ui_stage = BUTTON_STAGE_MAP.get(idx, "")
            enabled = ui_stage in {"text", "clean"} or is_stage_available(
                state,
                "render",
                target_lang=target_lang,
                has_runtime_patches=has_runtime_patches,
            )
            button.setEnabled(enabled)
            if hasattr(button, "set_dayu_type"):
                button.set_dayu_type(
                    MPushButton.PrimaryType if ui_stage == current_ui_stage and enabled else MPushButton.DefaultType
                )

    def restore_current_page_view(self) -> None:
        file_path = self._current_file_path()
        if not file_path or file_path not in self.main.image_states:
            self.refresh_stage_buttons(file_path)
            return
        self.apply_stage_view(file_path, self.get_ui_stage(file_path))

    def navigate_to_stage(self, ui_stage: str) -> None:
        file_path = self._current_file_path()
        if not file_path or ui_stage not in UI_STAGE_ORDER:
            return
        self.main.image_ctrl.save_current_image_state()
        self.apply_stage_view(file_path, ui_stage)

    def _run_clean_for_current_view(self, file_path: str) -> None:
        if not self.main.image_viewer.hasPhoto() or not self.main.image_viewer.has_drawn_elements():
            return
        state = self._get_state(file_path)
        self._set_ui_stage(state, "clean")
        self.main.image_ctrl.save_current_image_state()
        self.main.text_ctrl.clear_text_edits()
        self.main.loading.setVisible(True)
        self.main.disable_hbutton_group()
        self.main.undo_group.activeStack().beginMacro("clean")
        self.main.run_threaded(
            self.main.pipeline.inpaint,
            self.main.pipeline.inpaint_complete,
            self.main.default_error_handler,
            self.main.on_manual_finished,
        )

    def handle_stage_button(self, index: int) -> None:
        ui_stage = BUTTON_STAGE_MAP.get(index)
        if not ui_stage:
            return
        if ui_stage == "clean":
            file_path = self._current_file_path()
            if file_path and self.get_ui_stage(file_path) == "clean" and self.main.image_viewer.has_drawn_elements():
                self._run_clean_for_current_view(file_path)
                return
        self.navigate_to_stage(ui_stage)

    def _apply_invalidation_result(self, file_path: str, state: dict, ui_stage: str) -> None:
        self._set_ui_stage(state, ui_stage)
        self.refresh_stage_buttons(file_path)

    def invalidate_for_box_edit(self, file_path: str) -> None:
        state, ui_stage = invalidate_page_for_box_edit(
            self.main.image_states,
            self.main.image_patches,
            file_path,
        )
        self._apply_invalidation_result(file_path, state, ui_stage)

    def invalidate_for_source_text_edit(self, file_path: str) -> None:
        state, ui_stage = invalidate_page_for_source_text_edit(
            self.main.image_states,
            self.main.image_patches,
            file_path,
        )
        self._apply_invalidation_result(file_path, state, ui_stage)

    def invalidate_for_translated_text_edit(self, file_path: str, target_lang: str) -> None:
        state, ui_stage = invalidate_page_for_translated_text_edit(
            self.main.image_states,
            self.main.image_patches,
            file_path,
            target_lang,
        )
        self._apply_invalidation_result(file_path, state, ui_stage)

    def invalidate_for_format_edit(self, file_path: str, target_lang: str) -> None:
        state, ui_stage = invalidate_page_for_format_edit(
            self.main.image_states,
            self.main.image_patches,
            file_path,
            target_lang,
        )
        self._apply_invalidation_result(file_path, state, ui_stage)

    def invalidate_for_segmentation_edit(self, file_path: str) -> None:
        state, ui_stage = invalidate_page_for_segmentation_edit(
            self.main.image_states,
            self.main.image_patches,
            file_path,
        )
        self._apply_invalidation_result(file_path, state, ui_stage)

    def mark_clean_ready(self, file_path: str) -> None:
        state = self._get_state(file_path)
        mark_clean_ready(
            state,
            has_runtime_patches=page_has_runtime_patches(
                state,
                self.main.image_patches,
                file_path,
            ),
        )
        self.refresh_stage_buttons(file_path)
