from __future__ import annotations

import os
from functools import partial

from app.ui.messages import Messages
from modules.utils.pipeline_config import validate_settings
from pipeline.stage_state import activate_target_lang


class BatchUiMixin:
    def _start_batch_report(self, batch_paths: list[str]):
        self.batch_report_ctrl.start_batch_report(batch_paths)

    def _finalize_batch_report(self, was_cancelled: bool):
        return self.batch_report_ctrl.finalize_batch_report(was_cancelled)

    def show_latest_batch_report(self):
        self.batch_report_ctrl.show_latest_batch_report()

    def select_pages_with_errors(self):
        self.batch_report_ctrl.select_pages_with_errors()

    def register_batch_skip(self, image_path: str, skip_reason: str, error: str):
        self.batch_report_ctrl.register_batch_skip(image_path, skip_reason, error)

    def _sync_paths_to_active_target(self, image_paths: list[str]) -> None:
        active_target = self.t_combo.currentText()
        if not active_target:
            return
        for image_path in image_paths:
            state = self.image_states.setdefault(image_path, {})
            activate_target_lang(
                state,
                active_target,
                has_runtime_patches=bool(
                    state.get("inpaint_cache") or self.image_patches.get(image_path)
                ),
            )

    def _set_batch_ui_state(self, active: bool) -> None:
        self._batch_active = active
        if active:
            self._batch_cancel_requested = False
        self.translate_button.setEnabled(not active)
        self.cancel_button.setEnabled(True)
        self.save_as_project_button.setEnabled(not active)
        self.webtoon_toggle.setEnabled(not active)
        self.error_pages_button.setEnabled(False if active else self.error_pages_button.isEnabled())
        self.progress_bar.setVisible(active)

    def start_batch_process(self):
        try:
            if self._memlogger is not None:
                self._memlogger.emit("batch_start_all")
        except Exception:
            pass
        self.image_ctrl.save_current_image_state()
        self._sync_paths_to_active_target(self.image_files)
        for image_path in self.image_files:
            target_lang = self.image_states[image_path]["target_lang"]
            if not validate_settings(self, target_lang):
                return

        self.image_ctrl.clear_page_skip_errors_for_paths(self.image_files)
        self._start_batch_report(self.image_files)
        self._set_batch_ui_state(True)

        if self.webtoon_mode:
            self.run_threaded(
                self.pipeline.webtoon_batch_process,
                None,
                self.default_error_handler,
                self.on_batch_process_finished,
            )
        else:
            self.run_threaded(
                self.pipeline.batch_process,
                None,
                self.default_error_handler,
                self.on_batch_process_finished,
            )

    def batch_translate_selected(self, selected_file_names: list[str]):
        try:
            if self._memlogger is not None:
                self._memlogger.emit("batch_start_selected")
        except Exception:
            pass
        selected_paths: list[str] = []
        seen: set[str] = set()
        for ref in selected_file_names:
            path = ref if ref in self.image_files else None
            if path is None:
                path = next(
                    (candidate for candidate in self.image_files if os.path.basename(candidate) == ref),
                    None,
                )
            if path and path not in seen:
                selected_paths.append(path)
                seen.add(path)
        if not selected_paths:
            return

        self.image_ctrl.save_current_image_state()
        self._sync_paths_to_active_target(selected_paths)
        for path in selected_paths:
            target_lang = self.image_states[path]["target_lang"]
            if not validate_settings(self, target_lang):
                return

        self.image_ctrl.clear_page_skip_errors_for_paths(selected_paths)
        self._start_batch_report(selected_paths)
        self.selected_batch = selected_paths
        self._set_batch_ui_state(True)

        if self.webtoon_mode:
            self.run_threaded(
                partial(self.pipeline.webtoon_batch_process, selected_paths),
                None,
                self.default_error_handler,
                self.on_batch_process_finished,
            )
        else:
            self.run_threaded(
                partial(self.pipeline.batch_process, selected_paths),
                None,
                self.default_error_handler,
                self.on_batch_process_finished,
            )

    def on_batch_process_finished(self):
        try:
            if self._memlogger is not None:
                self._memlogger.emit("batch_finished")
        except Exception:
            pass
        was_cancelled = self._batch_cancel_requested
        report = self._finalize_batch_report(was_cancelled)
        self._batch_active = False
        self._batch_cancel_requested = False
        try:
            self.project_ctrl.flush_batch_project_autosave()
        except Exception:
            pass
        try:
            self.stage_nav_ctrl.restore_current_page_view()
        except Exception:
            self.stage_nav_ctrl.refresh_stage_buttons()
        self.progress_bar.setVisible(False)
        self.translate_button.setEnabled(True)
        self.cancel_button.setEnabled(True)
        self.save_as_project_button.setEnabled(True)
        self.webtoon_toggle.setEnabled(True)
        self.selected_batch = []
        if report and report["skipped_count"] > 0:
            self.error_pages_button.setEnabled(True)
        elif not was_cancelled:
            Messages.show_translation_complete(self)

        try:
            if self.pipeline is not None:
                self.pipeline.release_model_caches()
            if self._memlogger is not None:
                self._memlogger.emit("model_caches_released")
        except Exception:
            pass
