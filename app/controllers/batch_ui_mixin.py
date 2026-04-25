from __future__ import annotations

import os
from functools import partial

from app.ui.messages import Messages
from app.ui.main_window.constants import supported_target_languages
from modules.utils.pipeline_config import validate_settings
from pipeline.stage_state import activate_target_lang


MULTI_TRANSLATE_EXCLUDED_TARGETS = {"English"}


class BatchUiMixin:
    def _canonical_target_lang(self, target_lang: str) -> str:
        return self.lang_mapping.get(target_lang, target_lang)

    def _display_target_lang(self, target_lang: str) -> str:
        reverse_mapping = getattr(self, "reverse_lang_mapping", {}) or {}
        return reverse_mapping.get(target_lang, target_lang)

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
        self._sync_paths_to_target(image_paths, self.t_combo.currentText())

    def _sync_paths_to_target(self, image_paths: list[str], target_lang: str) -> None:
        if not target_lang:
            return
        for image_path in image_paths:
            state = self.image_states.setdefault(image_path, {})
            activate_target_lang(
                state,
                target_lang,
                has_runtime_patches=bool(
                    state.get("inpaint_cache") or self.image_patches.get(image_path)
                ),
            )

    def _set_batch_ui_state(self, active: bool) -> None:
        self._batch_active = active
        if active:
            self._batch_cancel_requested = False
        self.translate_button.setEnabled(not active)
        self.multi_translate_button.setEnabled(not active)
        self.cancel_button.setEnabled(True)
        self.save_as_project_button.setEnabled(not active)
        self.webtoon_toggle.setEnabled(not active)
        self.error_pages_button.setEnabled(False if active else self.error_pages_button.isEnabled())
        self.progress_bar.setVisible(active)

    def _multi_translate_targets(self) -> list[str]:
        # current_target = self._canonical_target_lang(self.t_combo.currentText())
        return [
            self._display_target_lang(lang)
            for lang in supported_target_languages
            if lang not in MULTI_TRANSLATE_EXCLUDED_TARGETS
            # and lang != current_target
            and self._canonical_target_lang(self._display_target_lang(lang)) == lang
        ]

    def start_multi_translate_process(self):
        if getattr(self, "_batch_active", False):
            return

        image_paths = list(self.image_files)
        if not image_paths:
            return

        targets = self._multi_translate_targets()
        if not targets:
            Messages.show_multi_translate_unavailable(self)
            return

        self.image_ctrl.save_current_image_state()
        for target_lang in targets:
            if not validate_settings(self, target_lang):
                return

        self._multi_translate_active = True
        self._multi_translate_queue = list(targets)
        self._multi_translate_paths = image_paths

        self.image_ctrl.clear_page_skip_errors_for_paths(image_paths)
        self._start_batch_report(image_paths)
        self.selected_batch = image_paths
        self._set_batch_ui_state(True)
        self._start_next_multi_translate_batch()

    def _start_next_multi_translate_batch(self):
        queue = getattr(self, "_multi_translate_queue", [])
        if not queue:
            self._finish_multi_translate_process(False)
            return

        target_lang = queue.pop(0)
        image_paths = list(getattr(self, "_multi_translate_paths", []) or [])
        self._sync_paths_to_target(image_paths, target_lang)

        if self.webtoon_mode:
            self.run_threaded(
                partial(self.pipeline.webtoon_batch_process, image_paths),
                None,
                self.default_error_handler,
                self.on_batch_process_finished,
            )
        else:
            self.run_threaded(
                partial(self.pipeline.batch_process, image_paths),
                None,
                self.default_error_handler,
                self.on_batch_process_finished,
            )

    def _finish_multi_translate_process(self, was_cancelled: bool):
        self._multi_translate_active = False
        self._multi_translate_queue = []
        self._multi_translate_paths = []

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
        self.multi_translate_button.setEnabled(True)
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
        if getattr(self, "_multi_translate_active", False):
            was_cancelled = self._batch_cancel_requested
            try:
                if self.pipeline is not None:
                    self.pipeline.release_model_caches()
            except Exception:
                pass
            if was_cancelled:
                self._finish_multi_translate_process(True)
            else:
                self._start_next_multi_translate_batch()
            return

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
        self.multi_translate_button.setEnabled(True)
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
