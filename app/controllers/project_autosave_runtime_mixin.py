from __future__ import annotations

import logging
import os

from PySide6 import QtCore
from PySide6.QtCore import QSettings

from app.projects.project_state import close_state_store
from app.thread_worker import GenericWorker

logger = logging.getLogger(__name__)


class ProjectAutosaveRuntimeMixin:
    def _init_project_autosave(self) -> None:
        self._autosave_timer = QtCore.QTimer(self.main)
        self._autosave_timer.setSingleShot(False)
        self._autosave_timer.timeout.connect(self._on_autosave_timeout)
        self._realtime_autosave_timer = QtCore.QTimer(self.main)
        self._realtime_autosave_timer.setSingleShot(True)
        self._realtime_autosave_timer.setInterval(800)
        self._realtime_autosave_timer.timeout.connect(self._on_realtime_autosave_timeout)
        self._batch_autosave_timer = QtCore.QTimer(self.main)
        self._batch_autosave_timer.setSingleShot(True)
        self._batch_autosave_timer.setInterval(1500)
        self._batch_autosave_timer.timeout.connect(self._perform_batch_project_autosave)
        self._autosave_signals_connected = False
        self._autosave_save_pending = False
        self._autosave_retrigger_requested = False
        self._batch_autosave_requested = False
        self._batch_autosave_last_image_path: str | None = None
        self._active_save_workers: list = []

    def _read_autosave_enabled_setting(self) -> bool:
        settings = QSettings("ComicLabs", "ComicTranslate")
        settings.beginGroup("export")
        value = settings.value("project_autosave_enabled", False, type=bool)
        settings.endGroup()
        return bool(value)

    def _write_autosave_enabled_setting(self, enabled: bool) -> None:
        settings = QSettings("ComicLabs", "ComicTranslate")
        settings.beginGroup("export")
        settings.setValue("project_autosave_enabled", bool(enabled))
        settings.endGroup()
        settings.sync()

    def initialize_autosave(self):
        persisted_enabled = self._read_autosave_enabled_setting()
        self.main.title_bar.set_autosave_checked(persisted_enabled)

        if self._autosave_signals_connected:
            self._apply_autosave_settings()
            return

        self.main.title_bar.autosave_switch.toggled.connect(self._on_autosave_setting_changed)
        self.main.settings_page.ui.project_autosave_interval_spinbox.valueChanged.connect(
            self._on_autosave_setting_changed
        )
        self._autosave_signals_connected = True
        self._apply_autosave_settings()

    def _on_autosave_setting_changed(self, *_):
        autosave_enabled = bool(self.main.title_bar.autosave_switch.isChecked())
        self._ensure_autosave_project_file_if_needed()
        try:
            self._write_autosave_enabled_setting(autosave_enabled)
        except Exception:
            logger.debug("Failed to persist autosave toggle directly.", exc_info=True)
        self._apply_autosave_settings()

    def _apply_autosave_settings(self):
        export_settings = self.main.settings_page.get_export_settings()
        interval_min = int(export_settings.get("project_autosave_interval_min", 3) or 3)
        interval_min = max(1, min(interval_min, 120))

        self._autosave_timer.setInterval(interval_min * 60 * 1000)
        self._autosave_timer.start()

    def _ensure_autosave_project_file_if_needed(self, require_images: bool = True) -> None:
        autosave_enabled = bool(
            self.main.settings_page.get_export_settings().get("project_autosave_enabled", False)
        )
        if not autosave_enabled or self.main.project_file:
            return
        if require_images and not self.main.image_files:
            return
        if self._is_startup_home_visible():
            return

        generated_project_file = self._generate_autosave_project_file_path()
        self.main.project_file = generated_project_file
        self.main.setWindowTitle(f"{os.path.basename(generated_project_file)}[*]")

    def ensure_autosave_project_file_for_new_project(self) -> None:
        self._ensure_autosave_project_file_if_needed(require_images=False)

    def shutdown_autosave(self, clear_recovery: bool = True):
        try:
            self._autosave_timer.stop()
        except Exception:
            pass
        try:
            self._realtime_autosave_timer.stop()
        except Exception:
            pass
        try:
            self._batch_autosave_timer.stop()
        except Exception:
            pass
        close_state_store()
        if clear_recovery:
            self.clear_recovery_checkpoint()

    def _on_autosave_timeout(self):
        self.autosave_project(prefer_project_file=False)

    def _on_realtime_autosave_timeout(self):
        self.autosave_project(prefer_project_file=True)

    def _schedule_batch_project_autosave(self, image_path: str | None = None, immediate: bool = False):
        autosave_enabled = bool(
            self.main.settings_page.get_export_settings().get("project_autosave_enabled", False)
        )
        if not autosave_enabled or not self.main.project_file:
            return

        self._batch_autosave_requested = True
        if image_path:
            self._batch_autosave_last_image_path = image_path

        if immediate:
            try:
                self._batch_autosave_timer.stop()
            except Exception:
                pass
            self._perform_batch_project_autosave()
            return

        self._batch_autosave_timer.start()

    def _perform_batch_project_autosave(self):
        autosave_enabled = bool(
            self.main.settings_page.get_export_settings().get("project_autosave_enabled", False)
        )
        if not autosave_enabled or not self.main.project_file:
            self._batch_autosave_requested = False
            return

        if not self._batch_autosave_requested:
            return

        if self._autosave_save_pending:
            self._autosave_retrigger_requested = True
            return

        autosave_start_revision = self.main._dirty_revision
        self._autosave_save_pending = True
        self._batch_autosave_requested = False
        target_file = self.main.project_file
        log_image_path = self._batch_autosave_last_image_path or target_file

        worker = GenericWorker(self.save_project, target_file)
        self._active_save_workers.append(worker)

        def on_error(error_tuple):
            try:
                self._active_save_workers.remove(worker)
            except ValueError:
                pass
            self._autosave_save_pending = False
            exctype, value, _ = error_tuple
            logger.warning("Batch autosave failed for %s: %s: %s", log_image_path, exctype.__name__, value)
            if self._autosave_retrigger_requested:
                self._autosave_retrigger_requested = False
                self._schedule_batch_project_autosave(self._batch_autosave_last_image_path)

        def on_finished():
            try:
                self._active_save_workers.remove(worker)
            except ValueError:
                pass
            self._autosave_save_pending = False
            self.clear_recovery_checkpoint()
            self.add_recent_project(target_file)
            self._refresh_home_screen()
            if self.main._dirty_revision == autosave_start_revision:
                self.main.set_project_clean()
            if self._autosave_retrigger_requested:
                self._autosave_retrigger_requested = False
                if getattr(self.main, "_batch_active", False):
                    self._schedule_batch_project_autosave(self._batch_autosave_last_image_path)
                else:
                    self._realtime_autosave_timer.start()

        worker.signals.error.connect(lambda err: QtCore.QTimer.singleShot(0, lambda: on_error(err)))
        worker.signals.finished.connect(lambda: QtCore.QTimer.singleShot(0, on_finished))
        self.main.threadpool.start(worker)

    def _on_batch_page_done(self, image_path: str):
        self._schedule_batch_project_autosave(image_path)

    def flush_batch_project_autosave(self):
        if self._batch_autosave_timer.isActive():
            self._batch_autosave_timer.stop()

        if self._autosave_save_pending:
            self._autosave_retrigger_requested = True
            self._batch_autosave_requested = True
            return

        if self._batch_autosave_requested:
            self._perform_batch_project_autosave()

    def notify_project_dirty_revision_changed(self):
        autosave_enabled = bool(
            self.main.settings_page.get_export_settings().get("project_autosave_enabled", False)
        )
        if not autosave_enabled:
            return
        self._ensure_autosave_project_file_if_needed()
        self._realtime_autosave_timer.start()

    def autosave_project(self, prefer_project_file: bool = True):
        if self._autosave_save_pending:
            if prefer_project_file:
                self._autosave_retrigger_requested = True
            return
        if not self.main.image_files or getattr(self.main, "_batch_active", False):
            return

        try:
            self.main.text_ctrl._commit_pending_text_command()
        except Exception:
            pass

        if not self.main.has_unsaved_changes():
            return

        self.save_current_state()

        autosave_enabled = bool(
            self.main.settings_page.get_export_settings().get("project_autosave_enabled", False)
        )
        self._ensure_autosave_project_file_if_needed()
        use_project_file = bool(prefer_project_file and autosave_enabled and self.main.project_file)
        target_file = self.main.project_file if use_project_file else self._recovery_project_path()
        if not target_file:
            return

        is_regular_project_save = bool(self.main.project_file and target_file == self.main.project_file)
        autosave_start_revision = self.main._dirty_revision
        self._autosave_save_pending = True

        def on_error(error_tuple):
            self._autosave_save_pending = False
            exctype, value, _ = error_tuple
            logger.warning("Project autosave failed: %s: %s", exctype.__name__, value)
            if self._autosave_retrigger_requested:
                self._autosave_retrigger_requested = False
                self._realtime_autosave_timer.start()

        def on_finished():
            self._autosave_save_pending = False
            if is_regular_project_save:
                self.clear_recovery_checkpoint()
                self.add_recent_project(target_file)
                self._refresh_home_screen()
                if self.main._dirty_revision == autosave_start_revision:
                    self.main.set_project_clean()
            if self._autosave_retrigger_requested or (is_regular_project_save and self.main.has_unsaved_changes()):
                self._autosave_retrigger_requested = False
                self._realtime_autosave_timer.start()

        self.main.run_threaded(self.save_project, None, on_error, on_finished, target_file)
