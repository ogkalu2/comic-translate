from __future__ import annotations

import os
import shutil
import tempfile
from typing import TYPE_CHECKING
from dataclasses import asdict, is_dataclass

from PySide6 import QtWidgets
from PySide6.QtCore import QSettings
from PySide6.QtGui import QUndoStack

from app.ui.canvas.save_renderer import ImageSaveRenderer
from app.projects.project_state import save_state_to_proj_file, load_state_from_proj_file
from modules.utils.archives import make

if TYPE_CHECKING:
    from controller import ComicTranslate
    

class ProjectController:
    def __init__(self, main: ComicTranslate):
        self.main = main

    def save_and_make(self, output_path: str):
        self.main.run_threaded(self.save_and_make_worker, None, self.main.default_error_handler, None, output_path)

    def save_and_make_worker(self, output_path: str):
        self.main.image_ctrl.save_current_image_state()
        temp_dir = tempfile.mkdtemp()
        try:
            # Save images
            for file_path in self.main.image_files:
                bname = os.path.basename(file_path)
                cv2_img = self.main.load_image(file_path)

                renderer = ImageSaveRenderer(cv2_img)
                viewer_state = self.main.image_states[file_path]['viewer_state']
                renderer.apply_patches(self.main.image_patches.get(file_path, []))
                renderer.add_state_to_image(viewer_state)
                sv_pth = os.path.join(temp_dir, bname)
                renderer.save_image(sv_pth)

            # Call make function
            make(temp_dir, output_path)
        finally:
            # Clean up temp directory
            shutil.rmtree(temp_dir)

    def launch_save_proj_dialog(self):
        file_dialog = QtWidgets.QFileDialog()
        file_name, _ = file_dialog.getSaveFileName(
            self.main,
            "Save Project As",
            "untitled",
            "Project Files (*.ctpr);;All Files (*)"
        )

        return file_name

    def run_save_proj(self, file_name):
        self.main.project_file = file_name
        self.main.loading.setVisible(True)
        self.main.disable_hbutton_group()
        self.main.run_threaded(self.save_project, None,
                                self.main.default_error_handler, self.main.on_manual_finished, file_name)

    def thread_save_project(self):
        file_name = ""
        self.main.image_ctrl.save_current_image_state()
        if self.main.project_file:
            file_name = self.main.project_file
        else:
            file_name = self.launch_save_proj_dialog()

        if file_name:
            self.run_save_proj(file_name)

    def thread_save_as_project(self):
        file_name = self.launch_save_proj_dialog()
        if file_name:
            self.main.image_ctrl.save_current_image_state()
            self.run_save_proj(file_name)

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
            self.main.undo_stacks[file] = stack
            self.main.undo_group.addStack(stack)

        self.main.run_threaded(
            lambda: self.main.load_image(self.main.image_files[index]),
            lambda result: self.main.image_ctrl.display_image_from_loaded(result, index, switch_page=False),
            self.main.default_error_handler,
            None
        )

    def thread_load_project(self, file_name):
        self.main.image_ctrl.clear_state()
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
        min_font_size = settings.value('min_font_size', 12)  # Default value is 12
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

