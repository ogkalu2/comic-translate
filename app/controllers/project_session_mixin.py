from __future__ import annotations

import os

from PySide6 import QtWidgets
from PySide6.QtGui import QUndoStack

from app.projects.project_state import close_state_store, load_state_from_proj_file, save_state_to_proj_file
from app.ui.commands.inpaint import PatchInsertCommand


class ProjectSessionMixin:
    def launch_save_proj_dialog(self):
        file_dialog = QtWidgets.QFileDialog()
        file_name, _ = file_dialog.getSaveFileName(
            self.main,
            "Save Project As",
            "untitled",
            "Project Files (*.ctpr);;All Files (*)",
        )

        return file_name

    def run_save_proj(self, file_name, post_save_callback=None):
        prev_project_file = self.main.project_file
        self.main.project_file = file_name
        self.main.setWindowTitle(f"{os.path.basename(file_name)}[*]")
        self.main.loading.setVisible(True)
        self.main.disable_hbutton_group()
        save_failed = {"value": False}
        save_start_revision = self.main._dirty_revision

        def on_error(error_tuple):
            save_failed["value"] = True
            self.main.default_error_handler(error_tuple)

        def on_finished():
            self.main.on_manual_finished()
            if not save_failed["value"]:
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

    def save_current_state(self):
        if self.main.webtoon_mode:
            webtoon_manager = self.main.image_viewer.webtoon_manager
            webtoon_manager.scene_item_manager.save_all_scene_items_to_states()
            webtoon_manager.save_view_state()
        else:
            self.main.image_ctrl.save_current_image_state()

    def thread_save_project(self, post_save_callback=None) -> bool:
        self.save_current_state()
        file_name = self.main.project_file or self.launch_save_proj_dialog()
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
        if not self.main.image_files:
            self.main.curr_img_idx = -1
            self.main.central_stack.setCurrentWidget(self.main.drag_browser)
            return

        index = self.main.curr_img_idx
        if not (0 <= index < len(self.main.image_files)):
            index = 0
            self.main.curr_img_idx = 0
        self.main.image_ctrl.update_image_cards()

        self.main.page_list.blockSignals(True)
        if 0 <= index < self.main.page_list.count():
            self.main.page_list.setCurrentRow(index)
            self.main.image_ctrl.highlight_card(index)
        self.main.page_list.blockSignals(False)

        for file_path in self.main.image_files:
            stack = QUndoStack(self.main)
            stack.cleanChanged.connect(self.main._update_window_modified)
            stack.indexChanged.connect(self.main._bump_dirty_revision)
            self.main.undo_stacks[file_path] = stack
            self.main.undo_group.addStack(stack)

        self._restore_inpaint_undo_history()
        self.main.image_ctrl.mark_text_stack_restore_pending()

        self.main.run_threaded(
            lambda: self.main.load_image(self.main.image_files[index]),
            lambda result: self._display_image_and_set_mode(result, index),
            self.main.default_error_handler,
        )

    def _restore_inpaint_undo_history(self):
        saved_patches = {
            file_path: [dict(patch) for patch in patch_list]
            for file_path, patch_list in self.main.image_patches.items()
            if patch_list
        }
        if not saved_patches:
            return

        self.main.image_patches = {}
        self.main.in_memory_patches.clear()

        for file_path, patch_list in saved_patches.items():
            stack = self.main.undo_stacks.get(file_path)
            if stack is None:
                self.main.image_patches[file_path] = patch_list
                continue

            grouped_patches: dict[str, list[dict]] = {}
            ordered_groups: list[str] = []
            for patch in patch_list:
                group_id = patch.get("group_id") or patch.get("hash")
                if group_id not in grouped_patches:
                    grouped_patches[group_id] = []
                    ordered_groups.append(group_id)
                grouped_patches[group_id].append(patch)

            for group_id in ordered_groups:
                stack.push(
                    PatchInsertCommand.from_saved_properties(
                        self.main,
                        grouped_patches[group_id],
                        file_path,
                    )
                )

    def _display_image_and_set_mode(self, rgb_image, index: int):
        self.main.image_ctrl.display_image_from_loaded(rgb_image, index, switch_page=False)

        if self.main.webtoon_mode:
            self.main.webtoon_toggle.setChecked(True)
            self.main.webtoon_ctrl.switch_to_webtoon_mode()
        self.main.set_project_clean()

    def _refresh_home_screen(self) -> None:
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
            normalized_path,
        )

    def load_project(self, file_name):
        if not os.path.isfile(file_name):
            raise FileNotFoundError(file_name)
        self.main.project_file = file_name
        return load_state_from_proj_file(self.main, file_name)

    def load_state_to_ui(self, saved_ctx: str):
        self.main.settings_page.ui.extra_context.setPlainText(saved_ctx)
