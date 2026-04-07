from __future__ import annotations

import copy
import logging
import os
import re
import shutil
import tempfile
from datetime import datetime
from typing import TYPE_CHECKING
from dataclasses import asdict, is_dataclass
from collections import OrderedDict

from PySide6 import QtWidgets, QtCore
from PySide6.QtCore import QSettings
from PySide6.QtGui import QUndoStack

from app.thread_worker import GenericWorker
from app.ui.dayu_widgets.message import MMessage
from app.ui.canvas.text_item import TextBlockItem
from app.ui.canvas.text.text_item_properties import TextItemProperties
from app.ui.canvas.save_renderer import ImageSaveRenderer
from app.ui.export_chapters_dialog import ExportChaptersDialog, ExportChapterRow
from app.controllers.psd_exporter import PsdPageData, export_psd_pages
from app.projects.project_state import (
    close_state_store,
    load_state_from_proj_file,
    remap_project_file_path,
    save_state_to_proj_file,
)
from modules.utils.archives import make
from modules.utils.paths import get_user_data_dir, get_default_project_autosave_dir

logger = logging.getLogger(__name__)

if TYPE_CHECKING:
    from controller import ComicTranslate
    

class ProjectController:
    def __init__(self, main: ComicTranslate):
        self.main = main
        self._autosave_timer = QtCore.QTimer(self.main)
        self._autosave_timer.setSingleShot(False)
        self._autosave_timer.timeout.connect(self._on_autosave_timeout)
        self._realtime_autosave_timer = QtCore.QTimer(self.main)
        self._realtime_autosave_timer.setSingleShot(True)
        self._realtime_autosave_timer.setInterval(800)
        self._realtime_autosave_timer.timeout.connect(self._on_realtime_autosave_timeout)
        self._autosave_signals_connected = False
        self._autosave_save_pending = False
        self._autosave_retrigger_requested = False
        self._active_save_workers: list = []  # keeps Python refs alive until workers finish
        self._last_project_dialog_dir = ""

    # Recent projects (persisted via QSettings)

    MAX_RECENT = 15

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

    def add_recent_project(self, path: str) -> None:
        """Push *path* to the front of the recent list; cap at MAX_RECENT."""
        if not path or not os.path.isfile(path):
            return
        path = os.path.normpath(os.path.abspath(path))
        entries = self.get_recent_projects()
        # Preserve pin state if already present
        existing = next((e for e in entries if os.path.normpath(e["path"]) == path), None)
        pinned = existing.get("pinned", False) if existing else False
        # Remove duplicates
        entries = [e for e in entries if os.path.normpath(e["path"]) != path]
        try:
            mtime = os.path.getmtime(path)
        except OSError:
            mtime = 0.0
        entries.insert(0, {"path": path, "mtime": mtime, "pinned": pinned})
        entries = entries[: self.MAX_RECENT]
        self._save_entries(entries)

    def get_recent_projects(self) -> list:
        """Return list of ``{path, mtime, pinned}`` dicts sorted by mtime desc."""
        settings = QSettings("ComicLabs", "ComicTranslate")
        settings.beginGroup("recent_projects")
        paths   = settings.value("paths",   []) or []
        mtimes  = settings.value("mtimes",  []) or []
        pinneds = settings.value("pinned",  []) or []
        settings.endGroup()
        # Normalise types — QSettings may return a single string if only 1 entry
        if isinstance(paths, str):   paths   = [paths]
        if not isinstance(mtimes,  list): mtimes  = [mtimes]
        if not isinstance(pinneds, list): pinneds = [pinneds]
        result = []
        for i, (path, mtime) in enumerate(zip(paths, mtimes)):
            try:
                m = float(mtime)
            except (TypeError, ValueError):
                m = 0.0
            # Refresh from filesystem when possible so ordering reflects real
            # modified time, not only the previously-saved snapshot.
            try:
                if os.path.isfile(path):
                    m = float(os.path.getmtime(path))
            except OSError:
                pass
            try:
                p = str(pinneds[i]).lower() == "true" if i < len(pinneds) else False
            except Exception:
                p = False
            result.append({"path": str(path), "mtime": m, "pinned": p})
        result.sort(key=lambda e: float(e.get("mtime", 0.0) or 0.0), reverse=True)
        return result

    def remove_recent_project(self, path: str) -> None:
        """Remove *path* from the recent list."""
        path = os.path.normpath(os.path.abspath(path))
        entries = [
            e for e in self.get_recent_projects()
            if os.path.normpath(e["path"]) != path
        ]
        self._save_entries(entries)

    def toggle_pin_project(self, path: str, pinned: bool) -> None:
        """Set the pinned flag for *path* and persist."""
        path = os.path.normpath(os.path.abspath(path))
        entries = self.get_recent_projects()
        for e in entries:
            if os.path.normpath(e["path"]) == path:
                e["pinned"] = pinned
                break
        self._save_entries(entries)

    def clear_recent_projects(self) -> None:
        """Wipe the entire recent list."""
        settings = QSettings("ComicLabs", "ComicTranslate")
        settings.beginGroup("recent_projects")
        settings.remove("")
        settings.endGroup()

    @staticmethod
    def _save_entries(entries: list) -> None:
        """Write the full entries list to QSettings."""
        settings = QSettings("ComicLabs", "ComicTranslate")
        settings.beginGroup("recent_projects")
        settings.setValue("paths",  [e["path"]           for e in entries])
        settings.setValue("mtimes", [e["mtime"]          for e in entries])
        settings.setValue("pinned", [e.get("pinned", False) for e in entries])
        settings.endGroup()

    def initialize_autosave(self):
        # Restore persisted auto-save toggle state as a single source of truth.
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

        # Defer auto-generating a project file until the user has actually
        # entered the workspace (not startup home) and loaded/started pages.
        self._ensure_autosave_project_file_if_needed()

        # Persist this key directly and sync so it is independent of UI widget
        # availability/order during shutdown.
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
        # Crash recovery snapshots remain interval-based.
        self._autosave_timer.start()

    def _is_startup_home_visible(self) -> bool:
        try:
            center_stack = self.main._center_stack
            home_screen = self.main.startup_home
            if center_stack is not None and home_screen is not None:
                return center_stack.currentWidget() is home_screen
        except Exception:
            pass
        return False

    def _ensure_autosave_project_file_if_needed(self, require_images: bool = True) -> None:
        autosave_enabled = bool(
            self.main.settings_page.get_export_settings().get("project_autosave_enabled", False)
        )
        if not autosave_enabled or self.main.project_file:
            return
        if require_images and not self.main.image_files:
            return
        # Avoid creating a "rogue" auto-save file on plain startup before user intent.
        if self._is_startup_home_visible():
            return

        generated_project_file = self._generate_autosave_project_file_path()
        self.main.project_file = generated_project_file
        self.main.setWindowTitle(f"{os.path.basename(generated_project_file)}[*]")

    def ensure_autosave_project_file_for_new_project(self) -> None:
        """Create an auto-save project file after explicit New Project intent."""
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
        close_state_store()
        if clear_recovery:
            self.clear_recovery_checkpoint()

    def _autosave_dir(self) -> str:
        return os.path.join(get_user_data_dir(), "autosave")

    def _recovery_project_path(self) -> str:
        return os.path.join(self._autosave_dir(), "project_recovery.ctpr")

    def _configured_project_autosave_dir(self) -> str:
        export_settings = self.main.settings_page.get_export_settings()
        configured_folder = str(export_settings.get("project_autosave_folder", "") or "").strip()
        if configured_folder:
            return configured_folder
        return get_default_project_autosave_dir()

    def _generate_autosave_project_file_path(self) -> str:
        autosave_dir = self._configured_project_autosave_dir()
        try:
            os.makedirs(autosave_dir, exist_ok=True)
        except Exception:
            logger.warning("Failed to create configured auto-save folder: %s", autosave_dir)
            autosave_dir = self._autosave_dir()
            os.makedirs(autosave_dir, exist_ok=True)

        base_name = "project"

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        candidate = os.path.join(autosave_dir, f"{base_name}_{timestamp}.ctpr")
        if not os.path.exists(candidate):
            return candidate

        for seq in range(1, 1000):
            seq_candidate = os.path.join(autosave_dir, f"{base_name}_{timestamp}_{seq:03d}.ctpr")
            if not os.path.exists(seq_candidate):
                return seq_candidate

        # Extremely unlikely fallback; keeps behavior deterministic if all sequence
        # slots are exhausted for the same timestamp.
        fallback_timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
        return os.path.join(autosave_dir, f"{base_name}_{fallback_timestamp}.ctpr")

    def clear_recovery_checkpoint(self):
        recovery_file = self._recovery_project_path()
        if os.path.exists(recovery_file):
            try:
                os.remove(recovery_file)
            except Exception:
                logger.debug("Failed to remove recovery project file: %s", recovery_file)

    def _on_autosave_timeout(self):
        # Interval timer is reserved for recovery checkpoints.
        self.autosave_project(prefer_project_file=False)

    def _on_realtime_autosave_timeout(self):
        # Real-time autosave writes directly to the open project file.
        self.autosave_project(prefer_project_file=True)

    def _on_batch_page_done(self, image_path: str):
        """Triggered by render_state_ready after each page is processed during batch.
        Saves the project file immediately so progress is not lost between pages.

        NOTE: this deliberately bypasses the task_runner_ctrl queue (which is
        blocked while the batch is running) and avoids touching current_worker
        (which the batch processor uses for cancel detection). A GenericWorker
        is started directly on the shared threadpool instead.
        """
        autosave_enabled = bool(
            self.main.settings_page.get_export_settings().get("project_autosave_enabled", False)
        )
        if not autosave_enabled or not self.main.project_file:
            return
        if self._autosave_save_pending:
            # A save is already in flight; request a follow-up once it finishes.
            self._autosave_retrigger_requested = True
            return

        autosave_start_revision = self.main._dirty_revision
        self._autosave_save_pending = True
        target_file = self.main.project_file

        worker = GenericWorker(self.save_project, target_file)
        self._active_save_workers.append(worker)  # prevent GC until done

        def on_error(error_tuple):
            try:
                self._active_save_workers.remove(worker)
            except ValueError:
                pass
            self._autosave_save_pending = False
            exctype, value, _ = error_tuple
            logger.warning("Per-page autosave failed for %s: %s: %s", image_path, exctype.__name__, value)
            if self._autosave_retrigger_requested:
                self._autosave_retrigger_requested = False
                self._on_batch_page_done(image_path)

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
                self._on_batch_page_done(image_path)

        worker.signals.error.connect(
            lambda err: QtCore.QTimer.singleShot(0, lambda: on_error(err))
        )
        worker.signals.finished.connect(
            lambda: QtCore.QTimer.singleShot(0, on_finished)
        )
        self.main.threadpool.start(worker)

    def notify_project_dirty_revision_changed(self):
        autosave_enabled = bool(
            self.main.settings_page.get_export_settings().get("project_autosave_enabled", False)
        )
        if not autosave_enabled:
            return
        self._ensure_autosave_project_file_if_needed()
        # Debounce bursts of edits (typing, drag, rapid undo/redo).
        # If no project file exists yet, autosave_project() falls back to
        # the recovery checkpoint path.
        self._realtime_autosave_timer.start()

    def autosave_project(self, prefer_project_file: bool = True):
        if self._autosave_save_pending:
            if prefer_project_file:
                self._autosave_retrigger_requested = True
            return
        if not self.main.image_files:
            return
        if getattr(self.main, "_batch_active", False):
            return

        # Flush pending text-edit command batching so autosave captures the latest edits.
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
            if self._autosave_retrigger_requested or (
                is_regular_project_save and self.main.has_unsaved_changes()
            ):
                self._autosave_retrigger_requested = False
                self._realtime_autosave_timer.start()

        self.main.run_threaded(self.save_project, None, on_error, on_finished, target_file)

    def prompt_restore_recovery_if_available(self) -> bool:
        if self.main.image_files:
            return False

        recovery_file = self._recovery_project_path()
        if not os.path.exists(recovery_file):
            return False

        saved_at = datetime.fromtimestamp(os.path.getmtime(recovery_file)).strftime("%Y-%m-%d %H:%M:%S")

        msg_box = QtWidgets.QMessageBox(self.main)
        msg_box.setIcon(QtWidgets.QMessageBox.Question)
        msg_box.setWindowTitle(self.main.tr("Project Recovery"))
        msg_box.setText(self.main.tr("An autosaved project from a previous session was found."))
        msg_box.setInformativeText(
            self.main.tr("Last autosave: {saved_at}\nDo you want to restore it?").format(saved_at=saved_at)
        )
        restore_btn = msg_box.addButton(self.main.tr("Restore"), QtWidgets.QMessageBox.ButtonRole.AcceptRole)
        discard_btn = msg_box.addButton(self.main.tr("Discard"), QtWidgets.QMessageBox.ButtonRole.DestructiveRole)
        msg_box.setDefaultButton(restore_btn)
        msg_box.exec()

        if msg_box.clickedButton() == restore_btn:
            self.restore_recovery_project(recovery_file)
            return True

        if msg_box.clickedButton() == discard_btn:
            self.clear_recovery_checkpoint()

        return False

    def restore_recovery_project(self, recovery_file: str | None = None):
        recovery_file = recovery_file or self._recovery_project_path()
        if not os.path.exists(recovery_file):
            return

        self.main.image_ctrl.clear_state()
        self.main.setWindowTitle(f"{self.main.tr('RecoveredProject.ctpr')}[*]")

        load_failed = {"value": False}

        def on_error(error_tuple):
            load_failed["value"] = True
            self.main.default_error_handler(error_tuple)

        def on_finished():
            if load_failed["value"]:
                return
            self.update_ui_from_project()
            # Keep recovered data as an unsaved project so users can choose a destination.
            self.main.project_file = None
            self.main.setWindowTitle(f"{self.main.tr('RecoveredProject.ctpr')}[*]")
            self.main.mark_project_dirty()
            self.clear_recovery_checkpoint()

        self.main.run_threaded(
            self.load_project,
            self.load_state_to_ui,
            on_error,
            on_finished,
            recovery_file,
        )

    def save_and_make(self, output_path: str):
        self._save_and_make_internal(output_path)

    def start_export_as(self, extension: str) -> None:
        extension = (extension or "").lower().lstrip(".")
        if not self.main.image_files:
            return

        export_rows = self._build_export_rows()
        if not self._should_show_partition_dialog(export_rows):
            output_path = self._launch_export_file_dialog(extension)
            if output_path:
                self._save_and_make_internal(output_path, skip_partition_dialog=True)
            return

        partition_result = self._prompt_for_partition(
            export_rows,
            os.path.join(self._get_default_export_dir(), f"untitled.{extension}"),
        )
        if partition_result is None:
            return
        chapter_names_by_path, output_dir = partition_result

        groups = self._group_page_indices(chapter_names_by_path)
        if len(groups) == 1:
            only_group_name = next(iter(groups.keys()))
            suggested_name = self._build_export_filename(only_group_name, f".{extension}", set())
            output_path = self._launch_export_file_dialog(
                extension,
                suggested_name=suggested_name,
                initial_dir=output_dir,
            )
            if output_path:
                self._save_and_make_internal(
                    output_path,
                    chapter_names_by_path=chapter_names_by_path,
                    skip_partition_dialog=True,
                )
            return

        export_plan = self._build_export_plan_for_directory(output_dir, f".{extension}", chapter_names_by_path)
        self._run_export_plan(export_plan)

    def _save_and_make_internal(
        self,
        output_path: str,
        chapter_names_by_path: dict[str, str] | None = None,
        skip_partition_dialog: bool = False,
    ) -> None:
        if not self.main.image_files:
            return

        export_rows = self._build_export_rows()
        resolved_chapter_names = chapter_names_by_path or {
            row.file_path: row.group_name for row in export_rows
        }
        if not skip_partition_dialog and self._should_show_partition_dialog(export_rows):
            partition_result = self._prompt_for_partition(export_rows, output_path)
            if partition_result is None:
                return
            resolved_chapter_names = partition_result[0]

        export_plan = self._build_export_plan(output_path, resolved_chapter_names)
        self._run_export_plan(export_plan)

    def _run_export_plan(self, export_plan: list[dict]) -> None:
        self.main.image_ctrl.save_current_image_state()
        all_pages_current_state = self._build_all_pages_current_state()
        self.main.loading.setVisible(True)
        self.main.run_threaded(
            self.save_and_make_worker,
            None,
            self.main.default_error_handler,
            lambda: self.main.loading.setVisible(False),
            export_plan,
            all_pages_current_state,
        )

    def _prompt_for_partition(
        self,
        export_rows: list[ExportChapterRow],
        output_path_hint: str,
    ) -> tuple[dict[str, str], str] | None:
        dialog = ExportChaptersDialog(
            export_rows,
            os.path.dirname(output_path_hint) or os.path.expanduser("~"),
            os.path.splitext(output_path_hint)[1],
            self._build_export_filename,
            parent=self.main,
        )
        if dialog.exec() != QtWidgets.QDialog.Accepted:
            return None
        chapter_names_by_path = dialog.chapter_names_by_path()
        self._persist_export_group_names(chapter_names_by_path)
        return chapter_names_by_path, dialog.selected_output_dir()

    def _persist_export_group_names(self, chapter_names_by_path: dict[str, str]) -> None:
        changed = False
        for file_path, group_name in chapter_names_by_path.items():
            state = self.main.image_states.setdefault(file_path, {})
            if state.get("export_group_name") != group_name:
                state["export_group_name"] = group_name
                changed = True
        if changed:
            self.main.mark_project_dirty()

    def _launch_export_file_dialog(
        self,
        extension: str,
        suggested_name: str | None = None,
        initial_dir: str | None = None,
    ) -> str:
        export_types = {
            "zip": "ZIP files (*.zip)",
            "cbz": "CBZ files (*.cbz)",
            "cb7": "CB7 files (*.cb7)",
            "pdf": "PDF files (*.pdf)",
        }
        normalized_ext = (extension or "").lower().lstrip(".")
        if normalized_ext not in export_types:
            return ""
        default_name = suggested_name or f"untitled.{normalized_ext}"
        selected_path, _ = QtWidgets.QFileDialog.getSaveFileName(
            self.main,
            "Save File",
            os.path.join(initial_dir or self._get_default_export_dir(), default_name),
            export_types[normalized_ext],
        )
        if not selected_path:
            return ""
        if not selected_path.lower().endswith(f".{normalized_ext}"):
            selected_path = f"{selected_path}.{normalized_ext}"
        return selected_path

    def export_to_psd_dialog(self):
        if not self.main.image_files:
            return

        default_dir = self._get_default_psd_export_dir()
        if len(self.main.image_files) == 1:
            default_name = f"{os.path.splitext(os.path.basename(self.main.image_files[0]))[0]}.psd"
            selected_path, _ = QtWidgets.QFileDialog.getSaveFileName(
                self.main,
                "Export PSD As",
                os.path.join(default_dir, default_name),
                "PSD Files (*.psd);;All Files (*)",
            )
            if not selected_path:
                return
            if not selected_path.lower().endswith(".psd"):
                selected_path = f"{selected_path}.psd"
            self.export_to_psd(os.path.dirname(selected_path), single_file_path=selected_path)
            return

        export_rows = self._build_export_rows()
        if self._should_show_partition_dialog(export_rows):
            partition_result = self._prompt_for_partition(
                export_rows,
                os.path.join(default_dir, "untitled.zip"),
            )
            if partition_result is None:
                return
            chapter_names_by_path, output_dir = partition_result
            export_plan = self._build_export_plan_for_directory(output_dir, ".zip", chapter_names_by_path)
            self.export_psd_plan(export_plan)
            return

        selected_folder = QtWidgets.QFileDialog.getExistingDirectory(
            self.main,
            "Export PSD",
            default_dir,
        )
        if selected_folder:
            self.export_to_psd(selected_folder)

    def export_to_psd(self, output_folder: str, single_file_path: str | None = None):
        # Gather all data on the main thread (GUI access required for scene items)
        self.main.image_ctrl.save_current_image_state()
        pages = self._gather_psd_pages()
        bundle_name = self._get_export_bundle_name()
        self.main.loading.setVisible(True)
        # Do the heavy PSD writing on the worker thread
        self.main.run_threaded(
            self._write_psd_worker, None, self.main.default_error_handler, lambda: self.main.loading.setVisible(False),
            output_folder, pages, bundle_name, single_file_path,
        )

    def export_psd_plan(self, export_plan: list[dict]) -> None:
        self.main.image_ctrl.save_current_image_state()
        pages = self._gather_psd_pages()
        self.main.loading.setVisible(True)
        self.main.run_threaded(
            self._write_psd_plan_worker,
            None,
            self.main.default_error_handler,
            lambda: self.main.loading.setVisible(False),
            export_plan,
            pages,
        )

    def _write_psd_worker(
        self,
        output_folder: str,
        pages: list[PsdPageData],
        bundle_name: str,
        single_file_path: str | None = None,
    ):
        export_psd_pages(
            output_folder=output_folder,
            pages=pages,
            bundle_name=bundle_name,
            single_file_path=single_file_path,
        )

    def _write_psd_plan_worker(
        self,
        export_plan: list[dict],
        pages: list[PsdPageData],
    ) -> None:
        for group in export_plan:
            group_pages = [
                pages[page_idx]
                for page_idx in group.get("page_indices", [])
                if 0 <= int(page_idx) < len(pages)
            ]
            if not group_pages:
                continue
            output_path = str(group.get("output_path") or "").strip()
            if not output_path:
                continue
            export_psd_pages(
                output_folder=os.path.dirname(output_path) or os.path.expanduser("~"),
                pages=group_pages,
                bundle_name=str(group.get("group_name") or self._get_export_bundle_name()),
                archive_path=output_path,
                archive_single_page=True,
            )

    @staticmethod
    def _sanitize_export_stem(value: str) -> str:
        sanitized = re.sub(r"[^A-Za-z0-9._-]+", "_", str(value or "").strip())
        return sanitized.strip("._-") or "chapter"

    def _default_export_group_name(self, file_path: str) -> str:
        state = self.main.image_states.get(file_path, {})
        group_name = str(state.get("export_group_name", "")).strip()
        if group_name:
            return group_name
        try:
            source_label = self.main.file_handler.get_prepared_source_label(file_path)
        except Exception:
            source_label = None
        if source_label:
            return source_label
        return self._get_export_bundle_name()

    def _build_export_rows(self) -> list[ExportChapterRow]:
        rows: list[ExportChapterRow] = []
        for page_index, file_path in enumerate(self.main.image_files):
            rows.append(
                ExportChapterRow(
                    page_index=page_index,
                    file_path=file_path,
                    file_name=os.path.basename(file_path),
                    group_name=self._default_export_group_name(file_path),
                )
            )
        return rows

    def _should_show_partition_dialog(self, rows: list[ExportChapterRow]) -> bool:
        if len(rows) <= 1:
            return False
        distinct_groups = {row.group_name for row in rows if row.group_name}
        if len(distinct_groups) > 1:
            return True
        basenames = [row.file_name.lower() for row in rows]
        return len(set(basenames)) != len(basenames)

    def _build_export_filename(self, group_name: str, extension: str, used_names: set[str]) -> str:
        ext = extension if str(extension).startswith(".") else f".{extension}"
        stem = self._sanitize_export_stem(group_name)
        candidate = f"{stem}{ext}"
        suffix = 2
        while candidate.lower() in used_names:
            candidate = f"{stem}_{suffix:02d}{ext}"
            suffix += 1
        used_names.add(candidate.lower())
        return candidate

    @staticmethod
    def _build_export_page_name(page_number: int, file_path: str) -> str:
        # Use the original filename directly
        basename = os.path.basename(file_path)
        # Sanitize the filename to remove any problematic characters
        stem = os.path.splitext(basename)[0]
        ext = os.path.splitext(basename)[1].lower() or ".png"
        stem = re.sub(r"[^A-Za-z0-9._-]+", "_", stem).strip("._-")
        if not stem:
            stem = f"page_{page_number:04d}"
        return f"{stem}{ext}"

    def _build_export_plan(self, output_path: str, chapter_names_by_path: dict[str, str]) -> list[dict]:
        extension = os.path.splitext(output_path)[1] or ".zip"
        output_dir = os.path.dirname(output_path) or os.path.expanduser("~")
        groups = self._group_page_indices(chapter_names_by_path)

        single_group = len(groups) == 1
        used_names: set[str] = set()
        plan: list[dict] = []
        for group_name, page_indices in groups.items():
            if single_group:
                group_output_path = output_path
            else:
                file_name = self._build_export_filename(group_name, extension, used_names)
                group_output_path = os.path.join(output_dir, file_name)
            plan.append({
                "group_name": group_name,
                "page_indices": page_indices,
                "output_path": group_output_path,
            })
        return plan

    def _build_export_plan_for_directory(
        self,
        output_dir: str,
        extension: str,
        chapter_names_by_path: dict[str, str],
    ) -> list[dict]:
        groups = self._group_page_indices(chapter_names_by_path)
        used_names: set[str] = set()
        plan: list[dict] = []
        for group_name, page_indices in groups.items():
            file_name = self._build_export_filename(group_name, extension, used_names)
            plan.append({
                "group_name": group_name,
                "page_indices": page_indices,
                "output_path": os.path.join(output_dir, file_name),
            })
        return plan

    def _group_page_indices(self, chapter_names_by_path: dict[str, str]) -> OrderedDict[str, list[int]]:
        groups: OrderedDict[str, list[int]] = OrderedDict()
        for page_index, file_path in enumerate(self.main.image_files):
            group_name = str(chapter_names_by_path.get(file_path) or self._default_export_group_name(file_path)).strip()
            groups.setdefault(group_name, []).append(page_index)
        return groups

    def save_and_make_worker(self, export_plan: list[dict], all_pages_current_state: dict[str, dict]):
        try:
            if self.main.file_handler.should_pre_materialize(self.main.image_files):
                count = self.main.file_handler.pre_materialize(self.main.image_files)
                logger.info("Export pre-materialized %d paths before save-and-make.", count)
        except Exception:
            logger.debug("Export pre-materialization failed; continuing lazily.", exc_info=True)
        temp_dir = tempfile.mkdtemp(prefix="comic_translate_export_")
        try:            
            temp_main_page_context = None
            if self.main.webtoon_mode:
                temp_main_page_context = type('TempMainPage', (object,), {
                    'image_files': self.main.image_files,
                    'image_states': all_pages_current_state
                })()

            for group_index, group in enumerate(export_plan, start=1):
                group_dir = os.path.join(temp_dir, f"group_{group_index:03d}")
                os.makedirs(group_dir, exist_ok=True)
                for page_number, page_idx in enumerate(group["page_indices"], start=1):
                    file_path = self.main.image_files[page_idx]
                    
                    # Try to load the image with error handling
                    try:
                        rgb_img = self.main.load_image(file_path)
                    except Exception as e:
                        print(f"Warning: Could not load image for page {page_idx} ({file_path}): {e}")
                        print(f"  Skipping this page in export")
                        continue
                    
                    renderer = ImageSaveRenderer(rgb_img)
                    viewer_state = all_pages_current_state[file_path]['viewer_state']

                    renderer.apply_patches(self.main.image_patches.get(file_path, []))
                    if self.main.webtoon_mode and temp_main_page_context is not None:
                        renderer.add_state_to_image(viewer_state, page_idx, temp_main_page_context)
                    else:
                        renderer.add_state_to_image(viewer_state)

                    sv_pth = os.path.join(group_dir, self._build_export_page_name(page_number, file_path))
                    renderer.save_image(sv_pth)

                os.makedirs(os.path.dirname(group["output_path"]) or ".", exist_ok=True)
                make(group_dir, group["output_path"])
        finally:
            # Clean up temp directory
            shutil.rmtree(temp_dir)

    def _gather_psd_pages(self) -> list[PsdPageData]:
        """Collect page data on the main thread where GUI access is safe."""
        all_pages_current_state = self._build_all_pages_current_state()

        temp_main_page_context = None
        if self.main.webtoon_mode:
            temp_main_page_context = type('TempMainPage', (object,), {
                'image_files': self.main.image_files,
                'image_states': all_pages_current_state
            })()

        pages: list[PsdPageData] = []
        for page_idx, file_path in enumerate(self.main.image_files):
            rgb_img = self.main.load_image(file_path)
            viewer_state = copy.deepcopy(all_pages_current_state[file_path].get('viewer_state', {}))

            if self.main.webtoon_mode and temp_main_page_context is not None:
                renderer = ImageSaveRenderer(rgb_img)
                renderer.add_spanning_text_items(viewer_state, page_idx, temp_main_page_context)

            patch_list = copy.deepcopy(self.main.image_patches.get(file_path, []))
            text_items = viewer_state.get('text_items_state', [])
            logger.info(
                "PSD page %d (%s): patches=%d, text_items=%d, viewer_state_keys=%s",
                page_idx, os.path.basename(file_path),
                len(patch_list), len(text_items) if text_items else 0,
                list(viewer_state.keys()),
            )

            pages.append(
                PsdPageData(
                    file_path=file_path,
                    rgb_image=rgb_img,
                    viewer_state=viewer_state,
                    patches=patch_list,
                )
            )

        return pages

    def _build_all_pages_current_state(self) -> dict[str, dict]:
        all_pages_current_state: dict[str, dict] = {}

        if self.main.webtoon_mode:
            loaded_pages = self.main.image_viewer.webtoon_manager.loaded_pages
            for page_idx, file_path in enumerate(self.main.image_files):
                if page_idx in loaded_pages:
                    viewer_state = self._create_text_items_state_from_scene(page_idx)
                else:
                    viewer_state = self.main.image_states.get(file_path, {}).get('viewer_state', {}).copy()
                all_pages_current_state[file_path] = {'viewer_state': viewer_state}
            return all_pages_current_state

        for file_path in self.main.image_files:
            viewer_state = self.main.image_states.get(file_path, {}).get('viewer_state', {}).copy()
            all_pages_current_state[file_path] = {'viewer_state': viewer_state}

        return all_pages_current_state

    def _get_export_bundle_name(self) -> str:
        if self.main.project_file:
            return os.path.splitext(os.path.basename(self.main.project_file))[0]
        if self.main.image_files:
            return os.path.splitext(os.path.basename(self.main.image_files[0]))[0]
        return "comic_translate_export"

    def _get_default_export_dir(self) -> str:
        if self.main.project_file:
            return os.path.dirname(self.main.project_file)
        if self.main.image_files:
            return os.path.dirname(self.main.image_files[0])
        return os.path.expanduser("~")

    def _create_text_items_state_from_scene(self, page_idx: int) -> dict:
        """
        Create text items state from current scene items for a loaded page in webtoon mode.
        An item "belongs" to a page if its origin point is within that page's vertical bounds.
        """
        
        webtoon_manager = self.main.image_viewer.webtoon_manager
        page_y_start = webtoon_manager.image_positions[page_idx]
        
        # Calculate page bottom boundary
        if page_idx < len(webtoon_manager.image_positions) - 1:
            page_y_end = webtoon_manager.image_positions[page_idx + 1]
        else:
            # For the last page, calculate its end based on its image height
            file_path = self.main.image_files[page_idx]
            rgb_img = self.main.load_image(file_path)
            page_y_end = page_y_start + rgb_img.shape[0]
        
        text_items_data = []
        
        # Find all text items that BELONG to this page
        for item in self.main.image_viewer._scene.items():
            if isinstance(item, TextBlockItem):
                text_item = item
                text_y = text_item.pos().y()
                
                # Check if the text item's origin is on this page
                if text_y >= page_y_start and text_y < page_y_end:
                    # Convert to page-local coordinates
                    scene_pos = text_item.pos()
                    page_local_x = scene_pos.x()
                    page_local_y = scene_pos.y() - page_y_start
                    
                    # Use TextItemProperties for consistent serialization
                    text_props = TextItemProperties.from_text_item(text_item)
                    # Override position to use page-local coordinates
                    text_props.position = (page_local_x, page_local_y)
                    
                    text_items_data.append(text_props.to_dict())
        
        # Return viewer state with the collected text items
        return {
            'text_items_state': text_items_data,
            'push_to_stack': False  # Don't push to undo stack during save
        }

    def launch_save_proj_dialog(self):
        file_dialog = QtWidgets.QFileDialog()
        initial_dir = self._get_default_project_dialog_dir()
        initial_path = os.path.join(initial_dir, "untitled.ctpr")
        file_name, _ = file_dialog.getSaveFileName(
            self.main,
            "Save Project As",
            initial_path,
            "Project Files (*.ctpr);;All Files (*)"
        )
        if file_name:
            self._last_project_dialog_dir = os.path.dirname(file_name)

        return file_name

    def _get_default_project_dialog_dir(self) -> str:
        if self._last_project_dialog_dir:
            return self._last_project_dialog_dir
        if self.main.project_file:
            return os.path.dirname(self.main.project_file)
        if self.main.image_files:
            return os.path.dirname(self.main.image_files[0])
        return os.path.expanduser("~")

    def run_save_proj(self, file_name, post_save_callback=None):
        prev_project_file = self.main.project_file
        prev_window_title = self.main.windowTitle()
        self.main.project_file = file_name
        self.main.setWindowTitle(f"{os.path.basename(file_name)}[*]")
        self.main.loading.setVisible(True)
        self.main.disable_hbutton_group()
        save_failed = {'value': False}
        save_start_revision = self.main._dirty_revision

        def on_error(error_tuple):
            save_failed['value'] = True
            self.main.project_file = prev_project_file
            self.main.setWindowTitle(prev_window_title)
            self.main.default_error_handler(error_tuple)

        def on_finished():
            self.main.on_manual_finished()
            if not save_failed['value']:
                # Close the old project's DB connection only after the save
                # has completed, so that lazy blobs can be read from it.
                if prev_project_file and prev_project_file != file_name:
                    close_state_store(prev_project_file)
                if self.main._dirty_revision == save_start_revision:
                    self.main.set_project_clean()
                self.clear_recovery_checkpoint()
                self.add_recent_project(file_name)
                self._refresh_home_screen()
                if post_save_callback:
                    post_save_callback()

        self.main.run_threaded(self.save_project, None, on_error, on_finished, file_name)

    def thread_change_project_file(self, target_path: str) -> bool:
        target_path = os.path.normpath(os.path.abspath(os.path.expanduser(target_path or "")))
        if not target_path:
            return False
        if not target_path.lower().endswith(".ctpr"):
            target_path = f"{target_path}.ctpr"

        current_path = (
            os.path.normpath(os.path.abspath(self.main.project_file))
            if self.main.project_file
            else None
        )

        target_dir = os.path.dirname(target_path)
        if not target_dir:
            QtWidgets.QMessageBox.warning(
                self.main,
                self.main.tr("Project File"),
                self.main.tr("Choose an existing folder for the project file."),
            )
            return False

        try:
            os.makedirs(target_dir, exist_ok=True)
        except OSError as exc:
            QtWidgets.QMessageBox.warning(
                self.main,
                self.main.tr("Project File"),
                self.main.tr(
                    "Could not create the selected project folder.\n\n{error}"
                ).format(error=str(exc)),
            )
            return False

        if current_path and target_path == current_path:
            return self.thread_save_project()

        if os.path.exists(target_path) and target_path != current_path:
            overwrite = QtWidgets.QMessageBox.question(
                self.main,
                self.main.tr("Overwrite Project File"),
                self.main.tr(
                    "A project file already exists at this location.\n\n{path}\n\nOverwrite it?"
                ).format(path=target_path),
                QtWidgets.QMessageBox.StandardButton.Yes | QtWidgets.QMessageBox.StandardButton.No,
                QtWidgets.QMessageBox.StandardButton.No,
            )
            if overwrite != QtWidgets.QMessageBox.StandardButton.Yes:
                return False

        if current_path and self._same_volume(current_path, target_path):
            return self._move_project_file(current_path, target_path)

        self.save_current_state()

        def _post_save() -> None:
            if current_path and current_path != target_path:
                removed_old_file = False
                if os.path.isfile(current_path):
                    try:
                        os.remove(current_path)
                        removed_old_file = True
                    except OSError as exc:
                        QtWidgets.QMessageBox.warning(
                            self.main,
                            self.main.tr("Old Project File Kept"),
                            self.main.tr(
                                "The project was saved to the new location, but the old file could not be removed.\n\n{path}\n\n{error}"
                            ).format(path=current_path, error=str(exc)),
                        )
                if removed_old_file or not os.path.exists(current_path):
                    self.remove_recent_project(current_path)
                    self._refresh_home_screen()

            MMessage.success(
                self.main.tr("Project file updated."),
                parent=self.main,
                duration=2,
            )

        self.run_save_proj(target_path, post_save_callback=_post_save)
        return True

    def _move_project_file(self, current_path: str, target_path: str) -> bool:
        if not os.path.isfile(current_path):
            return False

        try:
            remap_project_file_path(current_path, target_path)
            os.replace(current_path, target_path)
        except OSError as exc:
            try:
                remap_project_file_path(target_path, current_path)
            except OSError:
                pass
            QtWidgets.QMessageBox.warning(
                self.main,
                self.main.tr("Project File"),
                self.main.tr(
                    "Could not move the project file.\n\n{error}"
                ).format(error=str(exc)),
            )
            return False

        self.main.project_file = target_path
        self.main.setWindowTitle(f"{os.path.basename(target_path)}[*]")
        self.remove_recent_project(current_path)
        self.add_recent_project(target_path)
        self._refresh_home_screen()
        action_text = (
            self.main.tr("Project file renamed.")
            if os.path.dirname(current_path) == os.path.dirname(target_path)
            else self.main.tr("Project file moved.")
        )
        MMessage.success(
            action_text,
            parent=self.main,
            duration=2,
        )
        return True

    @staticmethod
    def _same_volume(path_a: str, path_b: str) -> bool:
        drive_a = os.path.splitdrive(os.path.abspath(path_a))[0].lower()
        drive_b = os.path.splitdrive(os.path.abspath(path_b))[0].lower()
        return drive_a == drive_b
        
    def save_current_state(self):
        if self.main.webtoon_mode:
            webtoon_manager = self.main.image_viewer.webtoon_manager
            webtoon_manager.scene_item_manager.save_all_scene_items_to_states()
            saved_view_state = webtoon_manager.save_view_state()
            saved_page_index = saved_view_state.get("current_page_index")
            if isinstance(saved_page_index, int):
                self.main.curr_img_idx = saved_page_index
            else:
                self.main.curr_img_idx = webtoon_manager.layout_manager.current_page_index
        else:
            self.main.image_ctrl.save_current_image_state()

    def thread_save_project(self, post_save_callback=None) -> bool:
        file_name = ""
        self.save_current_state()
        if self.main.project_file:
            file_name = self.main.project_file
        else:
            file_name = self.launch_save_proj_dialog()

        if file_name:
            self.run_save_proj(file_name, post_save_callback)
            return True
        return False

    def thread_save_as_project(self, post_save_callback=None) -> bool:
        file_name = self.launch_save_proj_dialog()
        if file_name:
            self.save_current_state()
            self.run_save_proj(file_name, post_save_callback)
            return True
        return False

    def save_project(self, file_name):
        save_state_to_proj_file(self.main, file_name)

    def update_ui_from_project(self):
        self.main.batch_report_ctrl.refresh_button_state()
        if not self.main.image_files:
            self.main.curr_img_idx = -1
            self.main.central_stack.setCurrentWidget(self.main.drag_browser)
            return

        index = self.main.curr_img_idx
        if self.main.webtoon_mode:
            saved_view_state = getattr(self.main.image_viewer, "webtoon_view_state", {}) or {}
            saved_page_index = saved_view_state.get("current_page_index")
            if isinstance(saved_page_index, int):
                index = saved_page_index
                self.main.curr_img_idx = saved_page_index
        if not (0 <= index < len(self.main.image_files)):
            index = 0
            self.main.curr_img_idx = 0
        self.main.image_ctrl.update_image_cards()

        # highlight the row that matches the current image
        self.main.page_list.blockSignals(True)
        if 0 <= index < self.main.page_list.count():
            self.main.page_list.setCurrentRow(index)
            self.main.image_ctrl.highlight_card(index)
        self.main.page_list.blockSignals(False)

        for file in self.main.image_files:
            stack = QUndoStack(self.main)
            stack.cleanChanged.connect(self.main._update_window_modified)
            stack.indexChanged.connect(self.main._bump_dirty_revision)
            self.main.undo_stacks[file] = stack
            self.main.undo_group.addStack(stack)

        self.main.run_threaded(
            lambda: self.main.load_image(self.main.image_files[index]),
            lambda result: self._display_image_and_set_mode(result, index),
            self.main.default_error_handler
        )

    def _display_image_and_set_mode(self, rgb_image, index: int):
        """Display the image and then set the appropriate mode."""
        # First display the image normally
        self.main.image_ctrl.display_image_from_loaded(rgb_image, index, switch_page=False)
        
        # Now that the UI is ready, activate webtoon mode
        if self.main.webtoon_mode:
            self.main.webtoon_toggle.setChecked(True)
            self.main.webtoon_ctrl.switch_to_webtoon_mode()
            QtCore.QTimer.singleShot(0, self.main.image_viewer.webtoon_manager.restore_view_state)
            QtCore.QTimer.singleShot(150, self.main.image_viewer.webtoon_manager.restore_view_state)
        self.main.set_project_clean()

    def _refresh_home_screen(self) -> None:
        """Repopulate the home screen recent list if it is currently visible."""
        home = self.main.startup_home
        if home is None:
            return
        home.populate(self.get_recent_projects())

    def thread_load_project(self, file_name: str, clear_recovery: bool = True):
        normalized_path = os.path.normpath(os.path.abspath(file_name))
        if not os.path.isfile(normalized_path):
            self.remove_recent_project(normalized_path)
            self._refresh_home_screen()
            self.main.setWindowTitle("Project1.ctpr[*]")
            self.main.project_file = None
            QtWidgets.QMessageBox.warning(
                self.main,
                self.main.tr("Project Not Found"),
                self.main.tr(
                    "The selected project file could not be found.\n"
                    "It may have been moved, renamed, or deleted.\n\n{path}"
                ).format(path=normalized_path),
            )
            return

        prev_project_file = self.main.project_file
        if prev_project_file and prev_project_file != normalized_path:
            close_state_store(prev_project_file)
        if clear_recovery:
            self.clear_recovery_checkpoint()
        self.main.image_ctrl.clear_state()
        self.main.setWindowTitle(f"{os.path.basename(normalized_path)}[*]")

        def _on_load_finished():
            self.add_recent_project(normalized_path)
            self._refresh_home_screen()
            self.update_ui_from_project()

        def _on_load_error(error_tuple):
            self.main.default_error_handler(error_tuple)
            exctype, value, _ = error_tuple
            self.main.project_file = None
            self.main.setWindowTitle("Project1.ctpr[*]")
            if exctype is FileNotFoundError or isinstance(value, FileNotFoundError):
                self.remove_recent_project(normalized_path)
                self._refresh_home_screen()

        self.main.run_threaded(
            self.load_project,
            self.load_state_to_ui,
            _on_load_error,
            _on_load_finished,
            normalized_path
        )

    def load_project(self, file_name):
        if not os.path.isfile(file_name):
            raise FileNotFoundError(file_name)
        self.main.project_file = file_name
        return load_state_from_proj_file(self.main, file_name)
    
    def load_state_to_ui(self, saved_ctx: str):
        self.main.settings_page.ui.extra_context.setPlainText(saved_ctx)

    def save_main_page_settings(self):
        settings = QSettings("ComicLabs", "ComicTranslate")

        self.process_group('text_rendering', self.main.render_settings(), settings)

        settings.beginGroup("main_page")
        # Save languages in English
        settings.setValue("source_language", self.main.lang_mapping[self.main.s_combo.currentText()])
        settings.setValue("target_language", self.main.lang_mapping[self.main.t_combo.currentText()])

        settings.setValue("mode", "manual" if self.main.manual_radio.isChecked() else "automatic")

        # Save brush and eraser sizes
        settings.setValue("brush_size", self.main.image_viewer.brush_size)
        settings.setValue("eraser_size", self.main.image_viewer.eraser_size)

        settings.endGroup()

        # Save window state
        settings.beginGroup("MainWindow")
        settings.setValue("geometry", self.main.saveGeometry())
        settings.setValue("state", self.main.saveState())
        settings.endGroup()

    def load_main_page_settings(self):
        settings = QSettings("ComicLabs", "ComicTranslate")
        settings.beginGroup("main_page")

        # Load languages and convert back to current language
        source_lang = settings.value("source_language", "Korean")
        target_lang = settings.value("target_language", "English")

        # Use reverse mapping to get the translated language names
        self.main.s_combo.setCurrentText(self.main.reverse_lang_mapping.get(source_lang, self.main.tr("Korean")))
        self.main.t_combo.setCurrentText(self.main.reverse_lang_mapping.get(target_lang, self.main.tr("English")))

        mode = settings.value("mode", "manual")
        if mode == "manual":
            self.main.manual_radio.setChecked(True)
            self.main.manual_mode_selected()
        else:
            self.main.automatic_radio.setChecked(True)
            self.main.batch_mode_selected()

        # Load brush and eraser sizes
        brush_size = int(settings.value("brush_size", 10))  # Default value is 10
        eraser_size = int(settings.value("eraser_size", 20))  # Default value is 20
        self.main.image_viewer.brush_size = brush_size
        self.main.image_viewer.eraser_size = eraser_size

        settings.endGroup()

        # Load window state
        settings.beginGroup("MainWindow")
        geometry = settings.value("geometry")
        state = settings.value("state")
        if geometry is not None:
            self.main.restoreGeometry(geometry)
        if state is not None:
            self.main.restoreState(state)
        settings.endGroup()

        # Load text rendering settings
        settings.beginGroup('text_rendering')
        alignment = settings.value('alignment_id', 1, type=int) # Default value is 1 which is Center
        self.main.alignment_tool_group.set_dayu_checked(alignment)

        saved_font_family = settings.value('font_family', '')
        if saved_font_family:
            self.main.set_font(saved_font_family)
        else:
            self.main.font_dropdown.setCurrentText('')
        min_font_size = settings.value('min_font_size', 5)  # Default value is 5
        max_font_size = settings.value('max_font_size', 40) # Default value is 40
        self.main.settings_page.ui.min_font_spinbox.setValue(int(min_font_size))
        self.main.settings_page.ui.max_font_spinbox.setValue(int(max_font_size))

        color = settings.value('color', '#000000')
        self.main.block_font_color_button.setStyleSheet(f"background-color: {color}; border: none; border-radius: 5px;")
        self.main.block_font_color_button.setProperty('selected_color', color)
        self.main.settings_page.ui.uppercase_checkbox.setChecked(settings.value('upper_case', False, type=bool))
        self.main.outline_checkbox.setChecked(settings.value('outline', True, type=bool))

        self.main.line_spacing_dropdown.setCurrentText(settings.value('line_spacing', '1.0'))
        self.main.outline_width_dropdown.setCurrentText(settings.value('outline_width', '1.0'))
        outline_color = settings.value('outline_color', '#FFFFFF')
        self.main.outline_font_color_button.setStyleSheet(f"background-color: {outline_color}; border: none; border-radius: 5px;")
        self.main.outline_font_color_button.setProperty('selected_color', outline_color)

        self.main.bold_button.setChecked(settings.value('bold', False, type=bool))
        self.main.italic_button.setChecked(settings.value('italic', False, type=bool))
        self.main.underline_button.setChecked(settings.value('underline', False, type=bool))
        settings.endGroup()

    def process_group(self, group_key, group_value, settings_obj: QSettings):
        """Helper function to process a group and its nested values."""
        if is_dataclass(group_value):
            group_value = asdict(group_value)
        if isinstance(group_value, dict):
            settings_obj.beginGroup(group_key)
            for sub_key, sub_value in group_value.items():
                self.process_group(sub_key, sub_value, settings_obj)
            settings_obj.endGroup()
        else:
            # Convert value to English using mappings if available
            mapped_value = self.main.settings_page.ui.value_mappings.get(group_value, group_value)
            settings_obj.setValue(group_key, mapped_value)

