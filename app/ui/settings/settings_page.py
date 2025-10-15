import os, shutil
from dataclasses import asdict, is_dataclass

from PySide6 import QtWidgets, QtGui
from PySide6.QtCore import Signal, QSettings
from PySide6.QtGui import QFont, QFontDatabase

from .settings_ui import SettingsPageUI

# Dictionary to map old model names to the newest versions in settings
OCR_MIGRATIONS = {
    "GPT-4o":       "GPT-4.1-mini",
    "Gemini-2.5-Flash": "Gemini-2.0-Flash",
}

TRANSLATOR_MIGRATIONS = {
    "GPT-4o":              "GPT-4.1",
    "GPT-4o mini":         "GPT-4.1-mini",
    "Gemini-2.0-Flash":    "Gemini-2.5-Flash",
    "Gemini-2.0-Pro":      "Gemini-2.5-Flash",
    "Gemini-2.5-Pro":      "Gemini-2.5-Flash",
    "Claude-3-Opus":       "Claude-4.5-Sonnet",
    "Claude-4-Sonnet":     "Claude-4.5-Sonnet",
    "Claude-3-Haiku":    "Claude-4.5-Haiku",
    "Claude-3.5-Haiku":   "Claude-4.5-Haiku",
}

INPAINTER_MIGRATIONS = {
    "MI-GAN": "AOT",
}

class SettingsPage(QtWidgets.QWidget):
    theme_changed = Signal(str)
    font_imported = Signal(str)

    def __init__(self, parent=None):
        super(SettingsPage, self).__init__(parent)

        self.ui = SettingsPageUI(self)
        self._setup_connections()
        self._loading_settings = False

        # Use the Settings UI directly; inner content is scrollable on the
        # right side (see settings_ui.py). This keeps the left navbar fixed.
        layout = QtWidgets.QVBoxLayout()
        layout.addWidget(self.ui)
        layout.setContentsMargins(0, 0, 0, 0)
        self.setLayout(layout)

    def _setup_connections(self):
        # Connect signals to slots
        self.ui.theme_combo.currentTextChanged.connect(self.on_theme_changed)
        self.ui.lang_combo.currentTextChanged.connect(self.on_language_changed)
        self.ui.font_browser.sig_files_changed.connect(self.import_font)

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
            'inpainter': self.ui.inpainter_combo,
            'detector': self.ui.detector_combo
        }
        return tool_combos[tool_type].currentText()

    def is_gpu_enabled(self):
        return self.ui.use_gpu_checkbox.isChecked()

    def get_llm_settings(self):
        return {
            'extra_context': self.ui.extra_context.toPlainText(),
            'image_input_enabled': self.ui.image_checkbox.isChecked(),
            'temperature': float(self.ui.temp_edit.text()),
            'top_p': float(self.ui.top_p_edit.text()),
            'max_tokens': int(self.ui.max_tokens_edit.text()),
        }

    def get_export_settings(self):
        settings = {
            'export_raw_text': self.ui.raw_text_checkbox.isChecked(),
            'export_translated_text': self.ui.translated_text_checkbox.isChecked(),
            'export_inpainted_image': self.ui.inpainted_image_checkbox.isChecked(),
            'save_as': {}
        }
        for file_type in self.ui.from_file_types:
            settings['save_as'][f'.{file_type}'] = self.ui.export_widgets[f'.{file_type}_save_as'].currentText()
        return settings

    def get_credentials(self, service: str = ""):
        save_keys = self.ui.save_keys_checkbox.isChecked()

        def _text_or_none(widget_key):
            w = self.ui.credential_widgets.get(widget_key)
            return w.text() if w is not None else None

        if service:
            creds = {'save_key': save_keys}
            if service == "Microsoft Azure":
                creds.update({
                    'api_key_ocr': _text_or_none("Microsoft Azure_api_key_ocr"),
                    'api_key_translator': _text_or_none("Microsoft Azure_api_key_translator"),
                    'region_translator': _text_or_none("Microsoft Azure_region"),
                    'endpoint': _text_or_none("Microsoft Azure_endpoint"),
                })
            elif service == "Custom":
                for field in ("api_key", "api_url", "model"):
                    creds[field] = _text_or_none(f"Custom_{field}")
            elif service == "Yandex":
                creds['api_key'] = _text_or_none("Yandex_api_key")
                creds['folder_id'] = _text_or_none("Yandex_folder_id")
            else:
                creds['api_key'] = _text_or_none(f"{service}_api_key")

            return creds

        # no `service` passed → recurse over all known services
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
                'detector': self.get_tool_selection('detector'),
                'inpainter': self.get_tool_selection('inpainter'),
                'use_gpu': self.is_gpu_enabled(),
                'hd_strategy': self.get_hd_strategy_settings()
            },
            'llm': self.get_llm_settings(),
            'export': self.get_export_settings(),
            'credentials': self.get_credentials(),
            'save_keys': self.ui.save_keys_checkbox.isChecked(),
        }

    def import_font(self, file_paths: list[str]):

        file_paths = [f for f in file_paths 
                      if f.endswith((".ttf", ".ttc", ".otf", ".woff", ".woff2"))]

        current_file_dir = os.path.dirname(os.path.abspath(__file__))
        project_root = os.path.abspath(os.path.join(current_file_dir, '..', '..', '..'))
        font_folder_path = os.path.join(project_root, 'resources', 'fonts')

        if not os.path.exists(font_folder_path):
            os.makedirs(font_folder_path)

        if file_paths:
            for file in file_paths:
                shutil.copy(file, font_folder_path)
                
            font_files = [os.path.join(font_folder_path, f) for f in os.listdir(font_folder_path) 
                      if f.endswith((".ttf", ".ttc", ".otf", ".woff", ".woff2"))]
            
            font_families = []
            for font in font_files:
                font_family = self.add_font_family(font)
                font_families.append(font_family)
            
            if font_families:
                self.font_imported.emit(font_families[0])

    def select_color(self, outline = False):
        default_color = QtGui.QColor('#000000') if not outline else QtGui.QColor('#FFFFFF')
        color_dialog = QtWidgets.QColorDialog()
        color_dialog.setCurrentColor(default_color)
        
        if color_dialog.exec() == QtWidgets.QDialog.Accepted:
            color = color_dialog.selectedColor()
            if color.isValid():
                button = self.ui.color_button if not outline else self.ui.outline_color_button
                button.setStyleSheet(
                    f"background-color: {color.name()}; border: none; border-radius: 5px;"
                )
                button.setProperty('selected_color', color.name())

    # With the mappings, settings are saved with English values and loaded in the selected language
    def save_settings(self):
        settings = QSettings("ComicLabs", "ComicTranslate")
        all_settings = self.get_all_settings()

        def process_group(group_key, group_value, settings_obj: QSettings):
            """Helper function to process a group and its nested values."""
            if is_dataclass(group_value):
                group_value = asdict(group_value)
            if isinstance(group_value, dict):
                settings_obj.beginGroup(group_key)
                for sub_key, sub_value in group_value.items():
                    process_group(sub_key, sub_value, settings_obj)
                settings_obj.endGroup()
            else:
                # Convert value to English using mappings if available
                mapped_value = self.ui.value_mappings.get(group_value, group_value)
                settings_obj.setValue(group_key, mapped_value)

        for key, value in all_settings.items():
            process_group(key, value, settings)

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
                elif translated_service == "Custom":
                    settings.setValue(f"{translated_service}_api_key", cred['api_key'])
                    settings.setValue(f"{translated_service}_api_url", cred['api_url'])
                    settings.setValue(f"{translated_service}_model", cred['model'])
                elif translated_service == "Yandex":
                    settings.setValue(f"{translated_service}_api_key", cred['api_key'])
                    settings.setValue(f"{translated_service}_folder_id", cred['folder_id'])
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
        raw_translator = settings.value('translator', 'GPT-4.1')
        translator = TRANSLATOR_MIGRATIONS.get(raw_translator, raw_translator)
        translated_translator = self.ui.reverse_mappings.get(translator, translator)
        self.ui.translator_combo.setCurrentText(translated_translator)

        raw_ocr = settings.value('ocr', 'Default')
        ocr = OCR_MIGRATIONS.get(raw_ocr, raw_ocr)
        translated_ocr = self.ui.reverse_mappings.get(ocr, ocr)
        self.ui.ocr_combo.setCurrentText(translated_ocr)

        raw_inpainter = settings.value('inpainter', 'LaMa')
        inpainter = INPAINTER_MIGRATIONS.get(raw_inpainter, raw_inpainter)
        translated_inpainter = self.ui.reverse_mappings.get(inpainter, inpainter)
        self.ui.inpainter_combo.setCurrentText(translated_inpainter)

        detector = settings.value('detector', 'RT-DETR-V2')
        translated_detector = self.ui.reverse_mappings.get(detector, detector)
        self.ui.detector_combo.setCurrentText(translated_detector)

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

        # Load LLM settings
        settings.beginGroup('llm')
        self.ui.extra_context.setPlainText(settings.value('extra_context', ''))
        self.ui.image_checkbox.setChecked(settings.value('image_input_enabled', False, type=bool))
        temp = settings.value('temperature', 1.0, type=float)
        self.ui.temp_edit.setText(f"{temp:.2f}")
        top_p = settings.value('top_p', 0.95, type=float)
        self.ui.top_p_edit.setText(f"{top_p:.2f}")
        max_tokens = settings.value('max_tokens', 4096, type=int)
        self.ui.max_tokens_edit.setText(str(max_tokens))
        settings.endGroup()

        # Load export settings
        settings.beginGroup('export')
        self.ui.raw_text_checkbox.setChecked(settings.value('export_raw_text', False, type=bool))
        self.ui.translated_text_checkbox.setChecked(settings.value('export_translated_text', False, type=bool))
        self.ui.inpainted_image_checkbox.setChecked(settings.value('export_inpainted_image', False, type=bool))
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
                translated_service = self.ui.value_mappings.get(service, service)
                if translated_service == "Microsoft Azure":
                    self.ui.credential_widgets["Microsoft Azure_api_key_ocr"].setText(settings.value(f"{translated_service}_api_key_ocr", ''))
                    self.ui.credential_widgets["Microsoft Azure_api_key_translator"].setText(settings.value(f"{translated_service}_api_key_translator", ''))
                    self.ui.credential_widgets["Microsoft Azure_region"].setText(settings.value(f"{translated_service}_region_translator", ''))
                    self.ui.credential_widgets["Microsoft Azure_endpoint"].setText(settings.value(f"{translated_service}_endpoint", ''))
                elif translated_service == "Custom":
                    self.ui.credential_widgets[f"{translated_service}_api_key"].setText(settings.value(f"{translated_service}_api_key", ''))
                    self.ui.credential_widgets[f"{translated_service}_api_url"].setText(settings.value(f"{translated_service}_api_url", ''))
                    self.ui.credential_widgets[f"{translated_service}_model"].setText(settings.value(f"{translated_service}_model", ''))
                elif translated_service == "Yandex":
                    self.ui.credential_widgets[f"{translated_service}_api_key"].setText(settings.value(f"{translated_service}_api_key", ''))
                    self.ui.credential_widgets[f"{translated_service}_folder_id"].setText(settings.value(f"{translated_service}_folder_id", ''))
                else:
                    self.ui.credential_widgets[f"{translated_service}_api_key"].setText(settings.value(f"{translated_service}_api_key", ''))
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

    def add_font_family(self, font_input: str) -> QFont:
        # Check if font_input is a file path
        if os.path.splitext(font_input)[1].lower() in [".ttf", ".ttc", ".otf", ".woff", ".woff2"]:
            font_id = QFontDatabase.addApplicationFont(font_input)
            if font_id != -1:
                font_families = QFontDatabase.applicationFontFamilies(font_id)
                if font_families:
                    return font_families[0]
        
        # If not a file path or loading failed, treat as font family name
        return font_input



