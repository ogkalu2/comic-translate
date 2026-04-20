from __future__ import annotations

from dataclasses import asdict, is_dataclass

from PySide6.QtCore import QSettings


class ProjectSettingsMixin:
    def save_main_page_settings(self):
        settings = QSettings("ComicLabs", "ComicTranslate")

        self.process_group("text_rendering", self.main.render_settings(), settings)

        settings.beginGroup("main_page")
        settings.setValue("target_language", self.main.lang_mapping[self.main.t_combo.currentText()])
        settings.setValue("ocr_language_hint", self.main.get_ocr_language_hint())
        settings.setValue("brush_size", self.main.image_viewer.brush_size)
        settings.setValue("eraser_size", self.main.image_viewer.eraser_size)
        settings.endGroup()

        settings.beginGroup("MainWindow")
        settings.setValue("geometry", self.main.saveGeometry())
        settings.setValue("state", self.main.saveState())
        settings.endGroup()

    def load_main_page_settings(self):
        settings = QSettings("ComicLabs", "ComicTranslate")
        settings.beginGroup("main_page")

        target_lang = settings.value("target_language", "English")
        self.main.t_combo.setCurrentText(self.main.reverse_lang_mapping.get(target_lang, self.main.tr("English")))
        ocr_language_hint = settings.value("ocr_language_hint", "Other Languages")
        self.main.ocr_language_combo.setCurrentText(
            self.main.reverse_ocr_language_hint_mapping.get(ocr_language_hint, self.main.tr("Other Languages"))
        )
        self.main.batch_mode_selected()

        brush_size = int(settings.value("brush_size", 10))
        eraser_size = int(settings.value("eraser_size", 20))
        self.main.image_viewer.brush_size = brush_size
        self.main.image_viewer.eraser_size = eraser_size

        settings.endGroup()

        settings.beginGroup("MainWindow")
        geometry = settings.value("geometry")
        state = settings.value("state")
        if geometry is not None:
            self.main.restoreGeometry(geometry)
        if state is not None:
            self.main.restoreState(state)
        settings.endGroup()

        settings.beginGroup("text_rendering")
        alignment = settings.value("alignment_id", 1, type=int)
        self.main.alignment_tool_group.set_dayu_checked(alignment)

        self.main.font_dropdown.setCurrentText(settings.value("font_family", ""))
        min_font_size = settings.value("min_font_size", 5)
        max_font_size = settings.value("max_font_size", 40)
        self.main.settings_page.ui.min_font_spinbox.setValue(int(min_font_size))
        self.main.settings_page.ui.max_font_spinbox.setValue(int(max_font_size))

        color = settings.value("color", "#000000")
        self.main.block_font_color_button.setStyleSheet(
            f"background-color: {color}; border: none; border-radius: 5px;"
        )
        self.main.block_font_color_button.setProperty("selected_color", color)
        self.main.settings_page.ui.uppercase_checkbox.setChecked(settings.value("upper_case", False, type=bool))
        self.main.outline_checkbox.setChecked(settings.value("outline", True, type=bool))

        self.main.line_spacing_dropdown.setCurrentText(settings.value("line_spacing", "1.0"))
        self.main.outline_width_dropdown.setCurrentText(settings.value("outline_width", "1.0"))
        outline_color = settings.value("outline_color", "#FFFFFF")
        self.main.outline_font_color_button.setStyleSheet(
            f"background-color: {outline_color}; border: none; border-radius: 5px;"
        )
        self.main.outline_font_color_button.setProperty("selected_color", outline_color)

        self.main.second_outline_checkbox.setChecked(settings.value("second_outline", False, type=bool))
        second_outline_color = settings.value("second_outline_color", "#000000")
        self.main.second_outline_color_button.setStyleSheet(
            f"background-color: {second_outline_color}; border: none; border-radius: 5px;"
        )
        self.main.second_outline_color_button.setProperty("selected_color", second_outline_color)
        self.main.second_outline_width_dropdown.setCurrentText(settings.value("second_outline_width", "1.0"))

        self.main.text_gradient_checkbox.setChecked(settings.value("text_gradient", False, type=bool))
        gradient_start = settings.value("text_gradient_start_color", color)
        gradient_end = settings.value("text_gradient_end_color", "#ffffff")
        self.main.text_gradient_start_button.setStyleSheet(
            f"background-color: {gradient_start}; border: none; border-radius: 5px;"
        )
        self.main.text_gradient_start_button.setProperty("selected_color", gradient_start)
        self.main.text_gradient_end_button.setStyleSheet(
            f"background-color: {gradient_end}; border: none; border-radius: 5px;"
        )
        self.main.text_gradient_end_button.setProperty("selected_color", gradient_end)

        self.main.bold_button.setChecked(settings.value("bold", False, type=bool))
        self.main.italic_button.setChecked(settings.value("italic", False, type=bool))
        self.main.underline_button.setChecked(settings.value("underline", False, type=bool))
        settings.endGroup()

    def process_group(self, group_key, group_value, settings_obj: QSettings):
        if is_dataclass(group_value):
            group_value = asdict(group_value)
        if isinstance(group_value, dict):
            settings_obj.beginGroup(group_key)
            for sub_key, sub_value in group_value.items():
                self.process_group(sub_key, sub_value, settings_obj)
            settings_obj.endGroup()
        else:
            mapped_value = self.main.settings_page.ui.value_mappings.get(group_value, group_value)
            settings_obj.setValue(group_key, mapped_value)
