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

    def _all_page_paths(self) -> list[str]:
        return list(getattr(self.main, "image_files", []) or [])

    def _save_visible_state_before_global_stage_change(self) -> None:
        if getattr(self.main, "webtoon_mode", False):
            manager = getattr(self.main.image_viewer, "webtoon_manager", None)
            scene_mgr = getattr(manager, "scene_item_manager", None) if manager is not None else None
            if scene_mgr is not None:
                scene_mgr.save_all_scene_items_to_states()
            return
        self.main.image_ctrl.save_current_image_state()

    def _any_page_has_blocks(self) -> bool:
        return any(
            bool((self.main.image_states.get(file_path) or {}).get("blk_list"))
            for file_path in self._all_page_paths()
        )

    def _page_has_clean_input(self, file_path: str) -> bool:
        state = self.main.image_states.get(file_path) or {}
        if state.get("brush_strokes"):
            return True
        return self._page_has_block_clean_input(file_path)

    def _page_has_block_clean_input(self, file_path: str) -> bool:
        state = self.main.image_states.get(file_path) or {}
        if not state.get("blk_list"):
            return False
        return not page_has_runtime_patches(state, self.main.image_patches, file_path)

    def _paths_with_clean_input(self) -> list[str]:
        file_paths = self._all_page_paths()
        stroke_paths = [
            file_path
            for file_path in file_paths
            if (self.main.image_states.get(file_path) or {}).get("brush_strokes")
        ]
        block_paths = [
            file_path
            for file_path in file_paths
            if file_path not in stroke_paths and self._page_has_block_clean_input(file_path)
        ]
        if stroke_paths:
            return stroke_paths + block_paths
        return block_paths

    def _seed_clean_strokes_for_page(self, file_path: str) -> None:
        page_ctx = self._get_page_context(file_path)
        self._get_segment_strokes(
            file_path,
            page_ctx.state,
            seed_from_blocks=not page_ctx.has_runtime_patches,
        )

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
            if ui_stage == "render":
                enabled = self._any_page_has_blocks() or is_stage_available(
                    state,
                    "render",
                    target_lang=target_lang,
                    has_runtime_patches=has_runtime_patches,
                )
            else:
                enabled = ui_stage in {"text", "clean"}
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

    def navigate_all_to_stage(self, ui_stage: str) -> None:
        if ui_stage not in UI_STAGE_ORDER:
            return
        file_paths = self._all_page_paths()
        if not file_paths:
            return

        self._save_visible_state_before_global_stage_change()
        for file_path in file_paths:
            state = self._get_state(file_path)
            self._set_ui_stage(state, ui_stage)
            if ui_stage == "clean":
                self._seed_clean_strokes_for_page(file_path)

        current_file = self._current_file_path()
        if current_file:
            self.apply_stage_view(current_file, ui_stage)
        else:
            self.refresh_stage_buttons()
        if hasattr(self.main, "mark_project_dirty"):
            self.main.mark_project_dirty()

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

    def _on_all_pages_clean_ready(self, page_results: list[tuple[str, list[dict]]]) -> None:
        for file_path, patches in page_results or []:
            if not patches:
                continue
            self.main.image_ctrl.on_inpaint_patches_processed(patches, file_path)
            state = self.main.image_states.get(file_path)
            if state is not None:
                state["brush_strokes"] = []

        current_file = self._current_file_path()
        if current_file:
            self.apply_stage_view(current_file, "clean")
        else:
            self.refresh_stage_buttons()
        if page_results and hasattr(self.main, "mark_project_dirty"):
            self.main.mark_project_dirty()

    def _run_clean_for_all_pages(self) -> None:
        self._save_visible_state_before_global_stage_change()
        file_paths = self._paths_with_clean_input()
        if not file_paths:
            return

        for file_path in self._all_page_paths():
            state = self._get_state(file_path)
            self._set_ui_stage(state, "clean")

        self.main.text_ctrl.clear_text_edits()
        self.main.loading.setVisible(True)
        self.main.disable_hbutton_group()
        self.main.run_threaded(
            lambda: self.main.pipeline.inpainting.inpaint_pages_from_states(file_paths),
            self._on_all_pages_clean_ready,
            self.main.default_error_handler,
            self.main.on_manual_finished,
        )

    def handle_stage_button(self, index: int) -> None:
        ui_stage = BUTTON_STAGE_MAP.get(index)
        if not ui_stage:
            return
        if ui_stage == "clean":
            file_path = self._current_file_path()
            if file_path and self.get_ui_stage(file_path) == "clean" and (
                self.main.image_viewer.has_drawn_elements() or self._paths_with_clean_input()
            ):
                self._run_clean_for_all_pages()
                return
            self.navigate_all_to_stage(ui_stage)
            return
        if ui_stage == "render" and self._any_page_has_blocks():
            self.main.text_ctrl.render_all_pages()
            return
        self.navigate_all_to_stage(ui_stage)

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
