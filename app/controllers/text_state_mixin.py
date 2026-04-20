from __future__ import annotations

import copy
from typing import TYPE_CHECKING

from PySide6 import QtCore

from app.ui.commands.box import ResizeBlocksCommand
from pipeline.render_state import ensure_target_snapshot, get_target_render_states, set_target_snapshot
from pipeline.translation_context import build_translation_prompt_context

from modules.utils.device import resolve_device
from modules.utils.language_utils import get_layout_direction

if TYPE_CHECKING:
    from modules.utils.textblock import TextBlock


class TextStateMixin:
    def clear_text_edits(self):
        self.main.curr_tblock = None
        self.main.curr_tblock_item = None
        self.main.s_text_edit.clear()
        self.main.t_text_edit.clear()

    def _current_file_path(self) -> str:
        if 0 <= self.main.curr_img_idx < len(self.main.image_files):
            return self.main.image_files[self.main.curr_img_idx]
        return ""

    def _current_target_lang(self) -> str:
        return self.main.t_combo.currentText()

    def _mirror_target_snapshot_to_viewer_state(self, state: dict, target_lang: str) -> dict:
        target_snapshot = get_target_render_states(state).get(target_lang)
        if not target_snapshot:
            target_snapshot = ensure_target_snapshot(
                state,
                target_lang,
                source_target=state.get("target_lang") or self._last_target_lang or "",
                fallback_snapshot=state.get("viewer_state") or {},
            )
        if target_snapshot:
            state["viewer_state"] = copy.deepcopy(target_snapshot)
        else:
            state.setdefault("viewer_state", {})
        return state["viewer_state"]

    def _sync_current_render_snapshot(self, file_path: str | None = None) -> None:
        file_path = file_path or self._current_file_path()
        if not file_path:
            return
        state = self.main.image_states.get(file_path)
        if state is None:
            return

        viewer_state = copy.deepcopy(state.get("viewer_state", {}) or {})
        if self.main.image_viewer.hasPhoto():
            current_scene_state = self.main.image_viewer.save_state()
            for key in ("transform", "center", "scene_rect"):
                if current_scene_state.get(key) is not None:
                    viewer_state[key] = current_scene_state.get(key)
            if self.main.image_viewer.text_items:
                viewer_state["text_items_state"] = copy.deepcopy(
                    current_scene_state.get("text_items_state", []) or []
                )

        state["viewer_state"] = viewer_state
        target_lang = state.get("target_lang") or self._current_target_lang()
        if target_lang and viewer_state.get("text_items_state") is not None:
            set_target_snapshot(state, target_lang, viewer_state)

    def _finalize_manual_render(self, current_file: str | None) -> None:
        batch_report_ctrl = getattr(self.main, "batch_report_ctrl", None)

        def _finish() -> None:
            try:
                if current_file is not None:
                    self.main.image_ctrl.save_image_state(current_file)
                if batch_report_ctrl is not None and current_file:
                    batch_report_ctrl.register_batch_success(current_file)
            finally:
                if self._manual_render_macro_open:
                    stack = self.main.undo_group.activeStack()
                    if stack is not None:
                        try:
                            stack.endMacro()
                        except Exception:
                            pass
                    self._manual_render_macro_open = False

        QtCore.QTimer.singleShot(0, _finish)

    def _sync_block_caches(
        self,
        blk: "TextBlock" | None,
        *,
        sync_ocr: bool = True,
        sync_translation: bool = True,
    ) -> None:
        if blk is None or self.main.curr_img_idx < 0 or self.main.curr_img_idx >= len(self.main.image_files):
            return

        current_file = self.main.image_files[self.main.curr_img_idx]
        try:
            image = self.main.image_ctrl.load_original_image(current_file)
        except Exception:
            image = None
        if image is None:
            return

        cache_manager = getattr(getattr(self.main, "pipeline", None), "cache_manager", None)
        if cache_manager is None:
            return

        settings_page = self.main.settings_page
        if sync_ocr:
            try:
                ocr_model = settings_page.get_tool_selection("ocr")
                ocr_language_hint = (
                    self.main.get_ocr_language_hint()
                    if hasattr(self.main, "get_ocr_language_hint")
                    else ""
                )
                device = resolve_device(settings_page.is_gpu_enabled())
                ocr_key = cache_manager._get_ocr_cache_key(image, ocr_language_hint, ocr_model, device)
                cache_manager.update_ocr_cache_for_block(ocr_key, blk)
            except Exception:
                pass

        if sync_translation:
            try:
                translator_key = settings_page.get_tool_selection("translator")
                target_lang = self.main.t_combo.currentText()
                _prompt_context, cache_signature = build_translation_prompt_context(
                    self.main,
                    self._current_file_path(),
                    target_lang,
                    llm_settings=settings_page.get_llm_settings(),
                )
                translation_key = cache_manager._get_translation_cache_key(
                    image,
                    "",
                    target_lang,
                    translator_key,
                    cache_signature,
                )
                cache_manager.update_translation_cache_for_block(translation_key, blk)
            except Exception:
                pass

    def save_src_trg(self):
        target_lang = self.main.t_combo.currentText()
        previous_target = self._last_target_lang
        if not previous_target and self.main.curr_img_idx >= 0:
            current_file = self.main.image_files[self.main.curr_img_idx]
            previous_target = self.main.image_states.get(current_file, {}).get("target_lang", "")

        self.main.image_ctrl.save_current_image_state()

        target_en = self.main.lang_mapping.get(target_lang, None)
        t_direction = get_layout_direction(target_en)
        t_text_option = self.main.t_text_edit.document().defaultTextOption()
        t_text_option.setTextDirection(t_direction)
        self.main.t_text_edit.document().setDefaultTextOption(t_text_option)

        for image_path in self.main.image_files:
            state = self.main.image_states.get(image_path)
            if state is not None:
                old_target = state.get("target_lang") or previous_target
                viewer_state = copy.deepcopy(state.get("viewer_state", {}) or {})
                target_render_states = get_target_render_states(state)
                if old_target and viewer_state and old_target not in target_render_states:
                    set_target_snapshot(state, old_target, viewer_state)

                had_target_snapshot = target_lang in target_render_states
                if not had_target_snapshot:
                    ensure_target_snapshot(
                        state,
                        target_lang,
                        source_target=old_target or "",
                        fallback_snapshot=viewer_state,
                    )
                if target_lang in target_render_states:
                    state["viewer_state"] = copy.deepcopy(target_render_states[target_lang])
                else:
                    state["viewer_state"] = viewer_state
                state["target_lang"] = target_lang
                if not had_target_snapshot:
                    ps = state.setdefault("pipeline_state", {})
                    target_validity = ps.setdefault("target_validity", {})
                    target_validity[target_lang] = {"translate": False, "render": False}

        if self.main.curr_img_idx >= 0:
            self.main.stage_nav_ctrl.restore_current_page_view()
            self.main.mark_project_dirty()
        self._last_target_lang = target_lang

    def set_src_trg_all(self):
        target_lang = self.main.t_combo.currentText()
        for image_path in self.main.image_files:
            state = self.main.image_states[image_path]
            target_render_states = get_target_render_states(state)
            if target_lang not in target_render_states and state.get("viewer_state"):
                set_target_snapshot(state, target_lang, state["viewer_state"])
            state["target_lang"] = target_lang
            if target_lang in target_render_states:
                state["viewer_state"] = copy.deepcopy(target_render_states[target_lang])
        if self.main.image_files:
            self.main.mark_project_dirty()

    def change_all_blocks_size(self, diff: int):
        if len(self.main.blk_list) == 0:
            return
        command = ResizeBlocksCommand(self.main, self.main.blk_list, diff)
        command.redo()
        current_file = self._current_file_path()
        if current_file:
            self.main.stage_nav_ctrl.invalidate_for_box_edit(current_file)
        self.main.mark_project_dirty()
