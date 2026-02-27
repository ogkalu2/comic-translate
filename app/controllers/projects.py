from __future__ import annotations

import copy
import logging
import os
import shutil
import tempfile
from datetime import datetime
from typing import TYPE_CHECKING
from dataclasses import asdict, is_dataclass
import imkit as imk

from PySide6 import QtWidgets, QtCore
from PySide6.QtCore import QSettings
from PySide6.QtGui import QUndoStack

from app.ui.canvas.text_item import TextBlockItem
from app.ui.canvas.text.text_item_properties import TextItemProperties
from app.ui.canvas.save_renderer import ImageSaveRenderer
from app.controllers.psd_exporter import PsdPageData, export_psd_pages
from app.projects.project_state import (
    close_state_store,
    load_state_from_proj_file,
    save_state_to_proj_file,
)
from modules.utils.archives import make
from modules.utils.paths import get_user_data_dir

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

    def initialize_autosave(self):
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

        # Word-like behavior: enabling autosave for an unsaved project must
        # first choose a concrete project file path.
        if autosave_enabled and not self.main.project_file:
            if not self.thread_save_as_project():
                with QtCore.QSignalBlocker(self.main.title_bar.autosave_switch):
                    self.main.title_bar.autosave_switch.setChecked(False)
                return

        self._apply_autosave_settings()

    def _apply_autosave_settings(self):
        export_settings = self.main.settings_page.get_export_settings()
        interval_min = int(export_settings.get("project_autosave_interval_min", 3) or 3)
        interval_min = max(1, min(interval_min, 120))

        self._autosave_timer.setInterval(interval_min * 60 * 1000)
        # Crash recovery snapshots remain interval-based.
        self._autosave_timer.start()

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

    def notify_project_dirty_revision_changed(self):
        if not self.main.project_file:
            return
        autosave_enabled = bool(
            self.main.settings_page.get_export_settings().get("project_autosave_enabled", False)
        )
        if not autosave_enabled:
            return
        # Debounce bursts of edits (typing, drag, rapid undo/redo).
        self._realtime_autosave_timer.start()

    def autosave_project(self, prefer_project_file: bool = True):
        if self._autosave_save_pending:
            if prefer_project_file:
                self._autosave_retrigger_requested = True
            return
        if not self.main.image_files:
            return
        if not self.main.has_unsaved_changes():
            return
        if getattr(self.main, "_batch_active", False):
            return

        # Flush pending text-edit command batching so autosave captures the latest edits.
        try:
            self.main.text_ctrl._commit_pending_text_command()
        except Exception:
            pass

        self.save_current_state()

        autosave_enabled = bool(
            self.main.settings_page.get_export_settings().get("project_autosave_enabled", False)
        )
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
        self.main.run_threaded(self.save_and_make_worker, None, self.main.default_error_handler, None, output_path)

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
        # Do the heavy PSD writing on the worker thread
        self.main.run_threaded(
            self._write_psd_worker, None, self.main.default_error_handler, None,
            output_folder, pages, bundle_name, single_file_path,
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

    def save_and_make_worker(self, output_path: str):
        self.main.image_ctrl.save_current_image_state()
        all_pages_current_state = self._build_all_pages_current_state()
        temp_dir = tempfile.mkdtemp()
        try:            
            temp_main_page_context = None
            if self.main.webtoon_mode:
                temp_main_page_context = type('TempMainPage', (object,), {
                    'image_files': self.main.image_files,
                    'image_states': all_pages_current_state
                })()

            for page_idx, file_path in enumerate(self.main.image_files):
                bname = os.path.basename(file_path)
                rgb_img = self.main.load_image(file_path)
                renderer = ImageSaveRenderer(rgb_img)
                viewer_state = all_pages_current_state[file_path]['viewer_state']

                renderer.apply_patches(self.main.image_patches.get(file_path, []))
                if self.main.webtoon_mode and temp_main_page_context is not None:
                    renderer.add_state_to_image(viewer_state, page_idx, temp_main_page_context)
                else:
                    renderer.add_state_to_image(viewer_state)

                sv_pth = os.path.join(temp_dir, bname)
                renderer.save_image(sv_pth)

            # Call make function
            make(temp_dir, output_path)
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

    def _get_default_psd_export_dir(self) -> str:
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
        file_name, _ = file_dialog.getSaveFileName(
            self.main,
            "Save Project As",
            "untitled",
            "Project Files (*.ctpr);;All Files (*)"
        )

        return file_name

    def run_save_proj(self, file_name, post_save_callback=None):
        prev_project_file = self.main.project_file
        if prev_project_file and prev_project_file != file_name:
            close_state_store(prev_project_file)
        self.main.project_file = file_name
        self.main.setWindowTitle(f"{os.path.basename(file_name)}[*]")
        self.main.loading.setVisible(True)
        self.main.disable_hbutton_group()
        save_failed = {'value': False}
        save_start_revision = self.main._dirty_revision

        def on_error(error_tuple):
            save_failed['value'] = True
            self.main.default_error_handler(error_tuple)

        def on_finished():
            self.main.on_manual_finished()
            if not save_failed['value']:
                if self.main._dirty_revision == save_start_revision:
                    self.main.set_project_clean()
                self.clear_recovery_checkpoint()
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
        index = self.main.curr_img_idx
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
        self.main.set_project_clean()

    def thread_load_project(self, file_name: str, clear_recovery: bool = True):
        prev_project_file = self.main.project_file
        if prev_project_file and prev_project_file != file_name:
            close_state_store(prev_project_file)
        if clear_recovery:
            self.clear_recovery_checkpoint()
        self.main.image_ctrl.clear_state()
        self.main.setWindowTitle(f"{os.path.basename(file_name)}[*]")
        self.main.run_threaded(
            self.load_project, 
            self.load_state_to_ui,
            self.main.default_error_handler, 
            self.update_ui_from_project, 
            file_name
        )

    def load_project(self, file_name):
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

        self.main.font_dropdown.setCurrentText(settings.value('font_family', ''))
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

