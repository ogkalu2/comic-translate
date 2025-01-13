import os, shutil
from typing import List

from PySide6 import QtWidgets, QtGui
from PySide6.QtCore import Signal, QSettings

from .settings_ui import SettingsPageUI

class SettingsPage(QtWidgets.QWidget):
    theme_changed = Signal(str)

    def __init__(self, parent=None):
        super(SettingsPage, self).__init__(parent)

        self.ui = SettingsPageUI(self)
        self._setup_connections()
        self._loading_settings = False

        layout = QtWidgets.QVBoxLayout()
        layout.addWidget(self.ui)
        self.setLayout(layout)

    def _setup_connections(self):
        # Connect signals to slots
        self.ui.theme_combo.currentTextChanged.connect(self.on_theme_changed)
        self.ui.lang_combo.currentTextChanged.connect(self.on_language_changed)
        self.ui.font_browser.sig_files_changed.connect(self.import_font)
        self.ui.color_button.clicked.connect(self.select_color)

    def on_theme_changed(self, theme: str):
        self.theme_changed.emit(theme)

    def get_language(self):
        return self.ui.lang_combo.currentText()
    
    def get_theme(self):
        return self.ui.theme_combo.currentText()

    def get_tool_selection(self, tool_type):
        tool_combos = {
            'translator': self.ui.translator_combo,
            'ocr': self.ui.ocr_combo,
            'inpainter': self.ui.inpainter_combo
        }
        return tool_combos[tool_type].currentText()

    def is_gpu_enabled(self):
        return self.ui.use_gpu_checkbox.isChecked()

    def get_text_rendering_settings(self):
        return {
            'alignment': self.ui.text_rendering_widgets['alignment'].currentText(),
            'font': self.ui.text_rendering_widgets['font'].currentText(),
            'min_font_size': self.get_min_font_size(),
            'max_font_size': self.get_max_font_size(),
            'color': self.ui.text_rendering_widgets['color_button'].property('selected_color'),
            'upper_case': self.ui.text_rendering_widgets['upper_case'].isChecked(),
            'outline': self.ui.text_rendering_widgets['outline'].isChecked(),
        }

    def get_llm_settings(self):
        return {
            'extra_context': self.ui.llm_widgets['extra_context'].toPlainText(),
            'image_input_enabled': self.ui.llm_widgets['image_input'].isChecked()
        }

    def get_export_settings(self):
        settings = {
            'export_raw_text': self.ui.export_widgets['raw_text'].isChecked(),
            'export_translated_text': self.ui.export_widgets['translated_text'].isChecked(),
            'export_inpainted_image': self.ui.export_widgets['inpainted_image'].isChecked(),
            'save_as': {}
        }
        for file_type in ['.pdf', '.epub', '.cbr', '.cbz', '.cb7', '.cbt']:
            settings['save_as'][file_type] = self.ui.export_widgets[f'{file_type}_save_as'].currentText()
        return settings

    def get_credentials(self, service: str = ""):
        save_keys = self.ui.save_keys_checkbox.isChecked()
        
        if service:
            if service == "Microsoft Azure":
                return {
                    'api_key_ocr': self.ui.credential_widgets["Microsoft Azure_api_key_ocr"].text(),
                    'api_key_translator': self.ui.credential_widgets["Microsoft Azure_api_key_translator"].text(),
                    'region_translator': self.ui.credential_widgets["Microsoft Azure_region"].text(),
                    'save_key': save_keys,
                    'endpoint': self.ui.credential_widgets["Microsoft Azure_endpoint"].text()
                }
            else:
                return {
                    'api_key': self.ui.credential_widgets[f"{service}_api_key"].text(),
                    'save_key': save_keys
                }
        else:
            return {s: self.get_credentials(s) for s in self.ui.credential_services}
        
    def get_hd_strategy_settings(self):
        strategy = self.ui.inpaint_strategy_combo.currentText()
        settings = {
            'strategy': strategy
        }

        if strategy == self.ui.tr("Resize"):
            settings['resize_limit'] = self.ui.resize_spinbox.value()
        elif strategy == self.ui.tr("Crop"):
            settings['crop_margin'] = self.ui.crop_margin_spinbox.value()
            settings['crop_trigger_size'] = self.ui.crop_trigger_spinbox.value()

        return settings

    def get_all_settings(self):
        return {
            'language': self.get_language(),
            'theme': self.get_theme(),
            'tools': {
                'translator': self.get_tool_selection('translator'),
                'ocr': self.get_tool_selection('ocr'),
                'inpainter': self.get_tool_selection('inpainter'),
                'use_gpu': self.is_gpu_enabled(),
                'hd_strategy': self.get_hd_strategy_settings()
            },
            'text_rendering': self.get_text_rendering_settings(),
            'llm': self.get_llm_settings(),
            'export': self.get_export_settings(),
            'credentials': self.get_credentials(),
            'save_keys': self.ui.save_keys_checkbox.isChecked()
        }

    def import_font(self, file_paths: List[str]):
        font_files = file_paths
        font_folder_path = os.path.join(os.getcwd(), "fonts")
        if not os.path.exists(font_folder_path):
            os.makedirs(font_folder_path)

        if font_files:
            for font_file in font_files:
                shutil.copy(font_file, font_folder_path)

            self.ui.font_combo.clear()
            font_files = [f for f in os.listdir(font_folder_path) if f.endswith((".ttf", ".ttc", ".otf", ".woff", ".woff2"))]
            self.ui.font_combo.addItems(font_files)
            filename = os.path.basename(font_files[0])
            self.ui.font_combo.setCurrentText(filename)

    def select_color(self):
        default_color = QtGui.QColor('#000000')  
        color_dialog = QtWidgets.QColorDialog()
        color_dialog.setCurrentColor(default_color)
        
        if color_dialog.exec() == QtWidgets.QDialog.Accepted:
            color = color_dialog.selectedColor()
            if color.isValid():
                self.ui.color_button.setStyleSheet(
                    f"background-color: {color.name()}; border: none; border-radius: 5px;"
                )
                self.ui.color_button.setProperty('selected_color', color.name())

    # With the mappings, settings are saved with English values and loaded in the selected language
    def save_settings(self):
        settings = QSettings("ComicLabs", "ComicTranslate")
        all_settings = self.get_all_settings()

        for key, value in all_settings.items():
            if isinstance(value, dict):
                settings.beginGroup(key)
                for sub_key, sub_value in value.items():
                    if isinstance(sub_value, dict):
                        settings.beginGroup(sub_key)
                        for sub_sub_key, sub_sub_value in sub_value.items():
                            # Convert value to English using mappings if available
                            mapped_value = self.ui.value_mappings.get(sub_sub_value, sub_sub_value)
                            settings.setValue(sub_sub_key, mapped_value)
                        settings.endGroup()
                    else:
                        # Convert value to English using mappings if available
                        mapped_value = self.ui.value_mappings.get(sub_value, sub_value)
                        settings.setValue(sub_key, mapped_value)
                settings.endGroup()
            else:
                # Convert value to English using mappings if available
                mapped_value = self.ui.value_mappings.get(value, value)
                settings.setValue(key, mapped_value)

        # Save credentials separately if save_keys is checked
        credentials = self.get_credentials()
        save_keys = self.ui.save_keys_checkbox.isChecked()
        settings.beginGroup('credentials')
        settings.setValue('save_keys', save_keys)
        if save_keys:
            for service, cred in credentials.items():
                translated_service = self.ui.value_mappings.get(service, service)
                if translated_service == "Microsoft Azure":
                    settings.setValue(f"{translated_service}_api_key_ocr", cred['api_key_ocr'])
                    settings.setValue(f"{translated_service}_api_key_translator", cred['api_key_translator'])
                    settings.setValue(f"{translated_service}_region_translator", cred['region_translator'])
                    settings.setValue(f"{translated_service}_endpoint", cred['endpoint'])
                else:
                    settings.setValue(f"{translated_service}_api_key", cred['api_key'])
        else:
            settings.remove('credentials')  # Clear all credentials if save_keys is unchecked
        settings.endGroup()

    def load_settings(self):
        self._loading_settings = True
        settings = QSettings("ComicLabs", "ComicTranslate")

        # Load language
        language = settings.value('language', 'English')
        translated_language = self.ui.reverse_mappings.get(language, language)
        self.ui.lang_combo.setCurrentText(translated_language)

        # Load theme
        theme = settings.value('theme', 'Dark')
        translated_theme = self.ui.reverse_mappings.get(theme, theme)
        self.ui.theme_combo.setCurrentText(translated_theme)
        self.theme_changed.emit(translated_theme)

        # Load tools settings
        settings.beginGroup('tools')
        # select GPT-4o as default
        translator = settings.value('translator', 'GPT-4o')
        # select Deepseek as default
        # translator = settings.value('translator', 'Deepseek-v3')
        translated_translator = self.ui.reverse_mappings.get(translator, translator)
        self.ui.translator_combo.setCurrentText(translated_translator)

        ocr = settings.value('ocr', 'Default')
        translated_ocr = self.ui.reverse_mappings.get(ocr, ocr)
        self.ui.ocr_combo.setCurrentText(translated_ocr)

        inpainter = settings.value('inpainter', 'LaMa')
        translated_inpainter = self.ui.reverse_mappings.get(inpainter, inpainter)
        self.ui.inpainter_combo.setCurrentText(translated_inpainter)

        self.ui.use_gpu_checkbox.setChecked(settings.value('use_gpu', False, type=bool))

        # Load HD strategy settings
        settings.beginGroup('hd_strategy')
        strategy = settings.value('strategy', 'Resize')
        translated_strategy = self.ui.reverse_mappings.get(strategy, strategy)
        self.ui.inpaint_strategy_combo.setCurrentText(translated_strategy)
        if strategy == 'Resize':
            self.ui.resize_spinbox.setValue(settings.value('resize_limit', 960, type=int))
        elif strategy == 'Crop':
            self.ui.crop_margin_spinbox.setValue(settings.value('crop_margin', 512, type=int))
            self.ui.crop_trigger_spinbox.setValue(settings.value('crop_trigger_size', 512, type=int))
        settings.endGroup()  # hd_strategy
        settings.endGroup()  # tools

        # Load text rendering settings
        settings.beginGroup('text_rendering')
        alignment = settings.value('alignment', 'Center')
        translated_alignment = self.ui.reverse_mappings.get(alignment, alignment)
        self.ui.text_rendering_widgets['alignment'].setCurrentText(translated_alignment)

        self.ui.text_rendering_widgets['font'].setCurrentText(settings.value('font', ''))
        min_font_size = settings.value('min_font_size', 12)  # Default value is 12
        max_font_size = settings.value('max_font_size', 40) # Default value is 40
        self.ui.min_font_spinbox.setValue(int(min_font_size))
        self.ui.max_font_spinbox.setValue(int(max_font_size))
        color = settings.value('color', '#000000')
        
        self.ui.text_rendering_widgets['color_button'].setStyleSheet(f"background-color: {color}; border: none; border-radius: 5px;")
        self.ui.text_rendering_widgets['color_button'].setProperty('selected_color', color)
        self.ui.text_rendering_widgets['upper_case'].setChecked(settings.value('upper_case', False, type=bool))
        self.ui.text_rendering_widgets['outline'].setChecked(settings.value('outline', True, type=bool))
        settings.endGroup()

        # Load LLM settings
        settings.beginGroup('llm')
        self.ui.llm_widgets['extra_context'].setPlainText(settings.value('extra_context', ''))
        self.ui.llm_widgets['image_input'].setChecked(settings.value('image_input_enabled', True, type=bool))
        settings.endGroup()

        # Load export settings
        settings.beginGroup('export')
        self.ui.export_widgets['raw_text'].setChecked(settings.value('export_raw_text', False, type=bool))
        self.ui.export_widgets['translated_text'].setChecked(settings.value('export_translated_text', False, type=bool))
        self.ui.export_widgets['inpainted_image'].setChecked(settings.value('export_inpainted_image', False, type=bool))
        settings.beginGroup('save_as')
        for file_type in ['.pdf', '.epub', '.cbr', '.cbz', '.cb7', '.cbt']:
            self.ui.export_widgets[f'{file_type}_save_as'].setCurrentText(settings.value(file_type, file_type[1:]))
        settings.endGroup()  # save_as
        settings.endGroup()  # export

        # Load credentials
        settings.beginGroup('credentials')
        save_keys = settings.value('save_keys', False, type=bool)
        self.ui.save_keys_checkbox.setChecked(save_keys)
        if save_keys:
            for service in self.ui.credential_services:
                translated_service = self.ui.reverse_mappings.get(service, service)
                if translated_service == "Microsoft Azure":
                    self.ui.credential_widgets["Microsoft Azure_api_key_ocr"].setText(settings.value(f"{translated_service}_api_key_ocr", ''))
                    self.ui.credential_widgets["Microsoft Azure_api_key_translator"].setText(settings.value(f"{translated_service}_api_key_translator", ''))
                    self.ui.credential_widgets["Microsoft Azure_region"].setText(settings.value(f"{translated_service}_region_translator", ''))
                    self.ui.credential_widgets["Microsoft Azure_endpoint"].setText(settings.value(f"{translated_service}_endpoint", ''))
                else:
                    self.ui.credential_widgets[f"{service}_api_key"].setText(settings.value(f"{translated_service}_api_key", ''))
        settings.endGroup()

        self._loading_settings = False

    def on_language_changed(self, new_language):
        if not self._loading_settings:  
            self.show_restart_dialog()

    def show_restart_dialog(self):
        msg_box = QtWidgets.QMessageBox(self)
        msg_box.setWindowTitle(self.tr("Restart Required"))
        msg_box.setText(self.tr("Please restart the application for the language changes to take effect."))
        msg_box.setIcon(QtWidgets.QMessageBox.Information)
        msg_box.setStandardButtons(QtWidgets.QMessageBox.Ok)
        msg_box.exec()

    def get_min_font_size(self):
        return int(self.ui.min_font_spinbox.value())
    
    def get_max_font_size(self):
        return int(self.ui.max_font_spinbox.value())



