import os, shutil, json
from typing import List

from PySide6 import QtWidgets, QtGui
from PySide6.QtCore import Signal, QSettings
from PySide6.QtGui import QFont, QFontDatabase

from .settings_ui import SettingsPageUI

from dataclasses import dataclass, asdict, is_dataclass

class SettingsPage(QtWidgets.QWidget):
    theme_changed = Signal(str)
    font_imported = Signal(str)
    selected_fonts_changed = Signal()  # Nuovo segnale per la modifica dei font selezionati

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
        self.selected_fonts_changed.connect(self._on_selected_fonts_changed)  # Connetti il segnale selected_fonts_changed

    def on_theme_changed(self, theme: str):
        self.theme_changed.emit(theme)

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

    def get_llm_settings(self):
        return {
            'extra_context': self.ui.extra_context.toPlainText(),
            'image_input_enabled': self.ui.image_checkbox.isChecked()
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
        
        if service:
            if service == "Microsoft Azure":
                return {
                    'api_key_ocr': self.ui.credential_widgets["Microsoft Azure_api_key_ocr"].text(),
                    'api_key_translator': self.ui.credential_widgets["Microsoft Azure_api_key_translator"].text(),
                    'region_translator': self.ui.credential_widgets["Microsoft Azure_region"].text(),
                    'save_key': save_keys,
                    'endpoint': self.ui.credential_widgets["Microsoft Azure_endpoint"].text()
                }
            elif service == "Custom":
                return {
                    'api_key': self.ui.credential_widgets[f"{service}_api_key"].text(),
                    'api_url': self.ui.credential_widgets[f"{service}_api_url"].text(),
                    'model': self.ui.credential_widgets[f"{service}_model"].text(),
                    'save_key': save_keys
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
            settings['resize_limit'] = str(self.ui.resize_spinbox.value())
        elif strategy == self.ui.tr("Crop"):
            settings['crop_margin'] = str(self.ui.crop_margin_spinbox.value())
            settings['crop_trigger_size'] = str(self.ui.crop_trigger_spinbox.value())

        return settings

    def get_all_settings(self):
        return {
            'language': self.ui.lang_combo.currentText(),
            'theme': self.get_theme(),
            'tools': {
                'translator': self.get_tool_selection('translator'),
                'ocr': self.get_tool_selection('ocr'),
                'inpainter': self.get_tool_selection('inpainter'),
                'use_gpu': self.is_gpu_enabled(),
                'hd_strategy': self.get_hd_strategy_settings()
            },
            'llm': self.get_llm_settings(),
            'export': self.get_export_settings(),
            'credentials': self.get_credentials(),
            'save_keys': self.ui.save_keys_checkbox.isChecked()
        }

    def import_font(self, file_paths: List[str]):

        file_paths = [f for f in file_paths 
                      if f.endswith((".ttf", ".ttc", ".otf", ".woff", ".woff2"))]

        current_file_dir = os.path.dirname(os.path.abspath(__file__))
        project_root = os.path.abspath(os.path.join(current_file_dir, '..', '..', '..'))
        font_folder_path = os.path.join(project_root, 'fonts')

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
        
        if color_dialog.exec() == QtWidgets.QDialog.DialogCode.Accepted:
            color = color_dialog.selectedColor()
            if color.isValid():
                # Check if the buttons exist before accessing them
                if hasattr(self.ui, 'color_button') and hasattr(self.ui, 'outline_color_button'):
                    button = self.ui.color_button if not outline else self.ui.outline_color_button
                    button.setStyleSheet(
                        f"background-color: {color.name()}; border: none; border-radius: 5px;"
                    )
                    button.setProperty('selected_color', color.name())

    # With the mappings, settings are saved with English values and loaded in the selected language
    def save_settings(self):
        settings = QSettings("ComicLabs", "CTkif 2_5 VL")
        all_settings = self.get_all_settings()

        def process_group(group_key: str, group_value, settings_obj: QSettings):
            """Helper function to process a group and its nested values."""
            if is_dataclass(group_value) and not isinstance(group_value, type):
                group_value = asdict(group_value)
            if isinstance(group_value, dict):
                settings_obj.beginGroup(str(group_key))
                for sub_key, sub_value in group_value.items():
                    process_group(str(sub_key), sub_value, settings_obj)
                settings_obj.endGroup()
            else:
                # Convert value to English using mappings if available
                mapped_value = self.ui.value_mappings.get(str(group_value), group_value)
                settings_obj.setValue(str(group_key), mapped_value)

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
                else:
                    settings.setValue(f"{translated_service}_api_key", cred['api_key'])
        else:
            settings.remove('credentials')  # Clear all credentials if save_keys is unchecked
        settings.endGroup()

        # Save selected fonts
        selected_fonts = self.get_selected_fonts()
        settings.beginGroup('text_rendering')
        settings.setValue('selected_fonts', selected_fonts)
        settings.endGroup()

    def load_settings(self):
        self._loading_settings = True
        settings = QSettings("ComicLabs", "CTkif 2_5 VL")

        # Load language
        language = settings.value('language', 'English', type=str)
        translated_language = self.ui.reverse_mappings.get(str(language), language)
        self.ui.lang_combo.setCurrentText(str(translated_language))

        # Load theme
        theme = settings.value('theme', 'Dark', type=str)
        translated_theme = self.ui.reverse_mappings.get(str(theme), theme)
        self.ui.theme_combo.setCurrentText(str(translated_theme))
        self.theme_changed.emit(str(translated_theme))

        # Load tools settings
        settings.beginGroup('tools')
        translator = settings.value('translator', 'GPT-4o', type=str)
        translated_translator = self.ui.reverse_mappings.get(str(translator), translator)
        self.ui.translator_combo.setCurrentText(str(translated_translator))

        ocr = settings.value('ocr', 'Default', type=str)
        translated_ocr = self.ui.reverse_mappings.get(str(ocr), ocr)
        self.ui.ocr_combo.setCurrentText(str(translated_ocr))

        inpainter = settings.value('inpainter', 'LaMa', type=str)
        translated_inpainter = self.ui.reverse_mappings.get(str(inpainter), inpainter)
        self.ui.inpainter_combo.setCurrentText(str(translated_inpainter))

        # Explicitly convert settings value to bool to avoid type mismatch
        use_gpu = bool(settings.value('use_gpu', False, type=bool))
        self.ui.use_gpu_checkbox.setChecked(use_gpu)

        # Load HD strategy settings
        settings.beginGroup('hd_strategy')
        strategy = settings.value('strategy', 'Resize', type=str)
        translated_strategy = self.ui.reverse_mappings.get(str(strategy), strategy)
        self.ui.inpaint_strategy_combo.setCurrentText(str(translated_strategy))
        if strategy == 'Resize':
            resize_limit = settings.value('resize_limit', 960)
            if isinstance(resize_limit, int):
                self.ui.resize_spinbox.setValue(resize_limit)
            else:
                self.ui.resize_spinbox.setValue(960)  # Default value if conversion fails
        elif strategy == 'Crop':
            crop_margin = settings.value('crop_margin', 512)
            crop_trigger = settings.value('crop_trigger_size', 512)
            
            if isinstance(crop_margin, int):
                self.ui.crop_margin_spinbox.setValue(crop_margin)
            else:
                self.ui.crop_margin_spinbox.setValue(512)  # Default value if conversion fails
                
            if isinstance(crop_trigger, int):
                self.ui.crop_trigger_spinbox.setValue(crop_trigger)
            else:
                self.ui.crop_trigger_spinbox.setValue(512)  # Default value if conversion fails
        settings.endGroup()  # hd_strategy
        settings.endGroup()  # tools

        # Load LLM settings
        settings.beginGroup('llm')
        extra_context = settings.value('extra_context', '', type=str)
        if extra_context is not None:
            self.ui.extra_context.setPlainText(str(extra_context))
        else:
            self.ui.extra_context.setPlainText('')
        image_input_enabled = bool(settings.value('image_input_enabled', True, type=bool))
        self.ui.image_checkbox.setChecked(image_input_enabled)
        settings.endGroup()

        # Load export settings
        settings.beginGroup('export')
        self.ui.raw_text_checkbox.setChecked(bool(settings.value('export_raw_text', False, type=bool)))
        self.ui.translated_text_checkbox.setChecked(bool(settings.value('export_translated_text', False, type=bool)))
        self.ui.inpainted_image_checkbox.setChecked(bool(settings.value('export_inpainted_image', False, type=bool)))
        settings.beginGroup('save_as')
        for file_type in ['.pdf', '.epub', '.cbr', '.cbz', '.cb7', '.cbt']:
            self.ui.export_widgets[f'{file_type}_save_as'].setCurrentText(settings.value(file_type, file_type[1:]))
        settings.endGroup()  # save_as
        settings.endGroup()  # export

        # Load credentials
        settings.beginGroup('credentials')
        save_keys = settings.value('save_keys', False, type=bool)
        self.ui.save_keys_checkbox.setChecked(bool(save_keys))
        if save_keys:
            for service in self.ui.credential_services:
                translated_service = self.ui.reverse_mappings.get(service, service)
                if translated_service == "Microsoft Azure":
                    self.ui.credential_widgets["Microsoft Azure_api_key_ocr"].setText(settings.value(f"{translated_service}_api_key_ocr", ''))
                    self.ui.credential_widgets["Microsoft Azure_api_key_translator"].setText(settings.value(f"{translated_service}_api_key_translator", ''))
                    self.ui.credential_widgets["Microsoft Azure_region"].setText(settings.value(f"{translated_service}_region_translator", ''))
                    self.ui.credential_widgets["Microsoft Azure_endpoint"].setText(settings.value(f"{translated_service}_endpoint", ''))
                elif translated_service == "Custom":
                    self.ui.credential_widgets[f"{service}_api_key"].setText(settings.value(f"{translated_service}_api_key", ''))
                    self.ui.credential_widgets[f"{service}_api_url"].setText(settings.value(f"{translated_service}_api_url", ''))
                    self.ui.credential_widgets[f"{service}_model"].setText(settings.value(f"{translated_service}_model", ''))
                else:
                    self.ui.credential_widgets[f"{service}_api_key"].setText(settings.value(f"{translated_service}_api_key", ''))
        settings.endGroup()

        # Load selected fonts
        settings.beginGroup('text_rendering')
        selected_fonts = settings.value('selected_fonts', [], type=list)
        settings.endGroup()
        self.set_selected_fonts(selected_fonts)

        self._loading_settings = False

    def on_language_changed(self, new_language):
        if not self._loading_settings:  
            self.show_restart_dialog()

    def show_restart_dialog(self):
        msg_box = QtWidgets.QMessageBox(self)
        msg_box.setWindowTitle(self.tr("Restart Required"))
        msg_box.setText(self.tr("Please restart the application for the language changes to take effect."))
        msg_box.setIcon(QtWidgets.QMessageBox.Icon.Information)
        msg_box.setStandardButtons(QtWidgets.QMessageBox.StandardButton.Ok)
        msg_box.exec()

    def get_min_font_size(self):
        return int(self.ui.min_font_spinbox.value())
    
    def get_max_font_size(self):
        return int(self.ui.max_font_spinbox.value())

    def add_font_family(self, font_input: str) -> str:
        # Check if font_input is a file path
        if os.path.splitext(font_input)[1].lower() in [".ttf", ".ttc", ".otf", ".woff", ".woff2"]:
            font_id = QFontDatabase.addApplicationFont(font_input)
            if font_id != -1:
                font_families = QFontDatabase.applicationFontFamilies(font_id)
                if font_families:
                    return font_families[0]
        
        # If not a file path or loading failed, treat as font family name
        return font_input

    def get_value(self, key: str, default_value=None):
        """Get a value from settings with a default fallback.
        
        Args:
            key: The settings key to retrieve
            default_value: Default value if key not found
            
        Returns:
            The value if found, otherwise the default value
        """
        # Handle credential keys
        if key.endswith('_api_key'):
            service = key.replace('_api_key', '')
            credentials = self.get_credentials(service)
            return credentials.get('api_key', default_value)
            
        # Handle other settings
        settings = self.get_all_settings()
        
        # Navigate nested dictionaries using dot notation
        try:
            value = settings
            for part in key.split('.'):
                value = value[part]
            return value
        except (KeyError, TypeError):
            return default_value

    # Removed duplicate get_theme method

    def get_qwen_ocr_prompt(self):
        """Gets the custom prompt for Qwen OCR."""
        current_file_dir = os.path.dirname(os.path.abspath(__file__))
        project_root = os.path.abspath(os.path.join(current_file_dir, '..', '..', '..'))
        prompts_path = os.path.join(project_root, 'config', 'prompts.json')
        
        try:
            with open(prompts_path, 'r', encoding='utf-8') as f:
                prompts = json.load(f)
                return prompts.get('qwen_ocr_prompt', 'Recognize the text in the image. Write exactly what appears, DO NOT translate.')
        except Exception as e:
            print(f"Error loading prompts: {e}")
            return 'Recognize the text in the image. Write exactly what appears, DO NOT translate.'

    def get_qwen_translate_prompt(self):
        """Ottiene il prompt personalizzato per il traduttore Qwen."""
        current_file_dir = os.path.dirname(os.path.abspath(__file__))
        project_root = os.path.abspath(os.path.join(current_file_dir, '..', '..', '..'))
        prompts_path = os.path.join(project_root, 'config', 'prompts.json')
        
        try:
            with open(prompts_path, 'r', encoding='utf-8') as f:
                prompts = json.load(f)
                return prompts.get('qwen_translate_prompt', '')
        except Exception as e:
            print(f"Error loading prompts: {e}")
            return ''

    def get_selected_fonts(self):
        """Restituisce la lista dei font selezionati nelle impostazioni"""
        selected_fonts = []
        for font_family, checkbox in self.ui.font_checkboxes.items():
            if checkbox.isChecked():
                selected_fonts.append(font_family)
        return selected_fonts

    def set_selected_fonts(self, selected_fonts):
        """Imposta i checkbox dei font"""
        # Se non ci sono font selezionati, seleziona tutti i font come default
        if not selected_fonts:
            for checkbox in self.ui.font_checkboxes.values():
                checkbox.setChecked(True)
        else:
            for font_family, checkbox in self.ui.font_checkboxes.items():
                checkbox.setChecked(font_family in selected_fonts)
        self.selected_fonts_changed.emit()  # Emit the signal when fonts are changed

    # Handler del segnale selected_fonts_changed
    def _on_selected_fonts_changed(self):
        # Salva le impostazioni quando i font selezionati cambiano
        self.save_font_settings()
        # Non emettiamo di nuovo il segnale qui per evitare un loop infinito

    def save_font_settings(self):
        # Salva solo le impostazioni dei font
        settings = QSettings("ComicLabs", "CTkif 2_5 VL")
        settings.beginGroup('text_rendering')
        selected_fonts = self.get_selected_fonts()
        settings.setValue('selected_fonts', selected_fonts)
        settings.endGroup()
