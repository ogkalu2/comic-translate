from __future__ import annotations

import logging
import os
from datetime import datetime

from PySide6 import QtWidgets

from modules.utils.paths import get_default_project_autosave_dir, get_user_data_dir

logger = logging.getLogger(__name__)


class ProjectRecoveryMixin:
    def _is_startup_home_visible(self) -> bool:
        try:
            center_stack = self.main._center_stack
            home_screen = self.main.startup_home
            if center_stack is not None and home_screen is not None:
                return center_stack.currentWidget() is home_screen
        except Exception:
            pass
        return False

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

        fallback_timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
        return os.path.join(autosave_dir, f"{base_name}_{fallback_timestamp}.ctpr")

    def clear_recovery_checkpoint(self):
        recovery_file = self._recovery_project_path()
        if os.path.exists(recovery_file):
            try:
                os.remove(recovery_file)
            except Exception:
                logger.debug("Failed to remove recovery project file: %s", recovery_file)

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
