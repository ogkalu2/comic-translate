import os, shutil
import socket
from typing import Any, Optional
import logging
from dataclasses import asdict, is_dataclass
import json

from PySide6 import QtWidgets, QtGui
from PySide6.QtCore import Signal, QSettings, QCoreApplication, QUrl, QTimer
from PySide6.QtGui import QFont, QFontDatabase
from PySide6.QtWebEngineWidgets import QWebEngineView 
from PySide6.QtWebEngineCore import QWebEngineProfile, QWebEnginePage

from .settings_ui import SettingsPageUI
from app.account.auth.auth_client import AuthClient, USER_INFO_GROUP, \
    EMAIL_KEY, TIER_KEY, CREDITS_KEY
from app.account.config import API_BASE_URL, FRONTEND_BASE_URL


logger = logging.getLogger(__name__)

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

class LoginWebViewDialog(QtWidgets.QDialog):
    """A simple dialog to host the QWebEngineView for login."""
    closed_manually = Signal()
    def __init__(self, url: str, parent=None):
        super().__init__(parent)
        self.setWindowTitle(QCoreApplication.translate("LoginWebViewDialog", "Sign In"))
        self.resize(500, 600)

        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(0,0,0,0)

        self.web_view = QWebEngineView()
        self.profile = QWebEngineProfile(parent=self.web_view) 
        page = QWebEnginePage(self.profile, self.web_view)
        self.web_view.setPage(page)
        layout.addWidget(self.web_view)
        self.web_view.load(QUrl(url))

    def closeEvent(self, event):
        logger.debug("LoginWebViewDialog closeEvent triggered.")
        # Stop any pending load
        self.web_view.stop()
        # If a page exists, schedule its deletion
        page = self.web_view.page()
        if page:
            page.deleteLater()
            self.web_view.setPage(None)
        # Schedule deletion of the profile explicitly
        if self.profile:
            self.profile.deleteLater()
        logger.debug("Closing login web view dialog.")
        super().closeEvent(event)

class SettingsPage(QtWidgets.QWidget):
    theme_changed = Signal(str)
    font_imported = Signal(str)
    login_state_changed = Signal(bool)

    def __init__(self, parent=None):
        super(SettingsPage, self).__init__(parent)

        self.ui = SettingsPageUI(self)
        self._setup_connections()
        self._loading_settings = False

        self.login_dialog: Optional[LoginWebViewDialog] = None
        self._pricing_refresh_timer: Optional[QTimer] = None
        self._pricing_refresh_attempts: int = 0
        self._pricing_refresh_baseline: Optional[Any] = None
        self.auth_client = AuthClient(API_BASE_URL, FRONTEND_BASE_URL)
        self.auth_client.auth_success.connect(self.handle_auth_success)
        self.auth_client.auth_error.connect(self.handle_auth_error)
        self.auth_client.auth_cancelled.connect(self.handle_auth_cancelled)
        self.auth_client.request_login_view.connect(self.show_login_view)
        self.auth_client.logout_success.connect(self.handle_logout_success)
        self.auth_client.session_check_finished.connect(self.handle_session_check_finished)

        self.user_email: Optional[str] = None
        self.user_tier: Optional[str] = None
        self.user_credits: Optional[Any] = None

        # Use the Settings UI directly; inner content is scrollable on the
        # right side (see settings_ui.py). This keeps the left navbar fixed.
        layout = QtWidgets.QVBoxLayout()
        layout.addWidget(self.ui)
        layout.setContentsMargins(0, 0, 0, 0)
        self.setLayout(layout)
        self._refresh_credits_on_startup()

    def _is_online(self) -> bool:
        try:
            socket.create_connection(("8.8.8.8", 53), 2)
            return True
        except OSError:
            return False

    def _refresh_credits_on_startup(self):
        """If there’s a network and an existing login, fetch fresh credits."""
        if self._is_online() and self.auth_client.validate_token():
            self.auth_client.fetch_user_info()

    def _setup_connections(self):
        # Connect signals to slots
        self.ui.theme_combo.currentTextChanged.connect(self.on_theme_changed)
        self.ui.lang_combo.currentTextChanged.connect(self.on_language_changed)
        self.ui.font_browser.sig_files_changed.connect(self.import_font)
        self.ui.sign_in_button.clicked.connect(self.start_sign_in)
        self.ui.buy_credits_button.clicked.connect(self.open_pricing_page)
        self.ui.sign_out_button.clicked.connect(self.sign_out)

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
    
    def get_user_info(self):
        """Returns the current user information."""
        return {
            'email': self.user_email,
            'tier': self.user_tier,
            'credits': self.user_credits
        }

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
            'user_info': self.get_user_info()
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
        
        # Default mappings for file format conversion
        default_save_as = {
            '.pdf': 'pdf',
            '.epub': 'pdf',
            '.cbr': 'cbz',
            '.cbz': 'cbz',
            '.cb7': 'cb7',
            '.cbt': 'cbz',
            '.zip': 'zip',
            '.rar': 'zip'
        }
        
        for file_type in self.ui.from_file_types:
            file_ext = f'.{file_type}'
            default_value = default_save_as.get(file_ext, file_type)
            self.ui.export_widgets[f'{file_ext}_save_as'].setCurrentText(settings.value(file_ext, default_value))
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

        # ADDED: Load user info and update account view 
        self._load_user_info_from_settings()
        self._update_account_view()
        # Emit initial login state
        self.login_state_changed.emit(self.is_logged_in())

        # Check session validity if logged in
        if self.is_logged_in():
            self.auth_client.check_session_async()
        # END Load user info 

        self._loading_settings = False

    # ADDED: Methods to load/save user info specifically
    def _load_user_info_from_settings(self):
        """Loads user information from QSettings."""
        logger.debug("Loading user info from settings...")
        settings = QSettings("ComicLabs", "ComicTranslate")
        settings.beginGroup(USER_INFO_GROUP)
        self.user_email = settings.value(EMAIL_KEY, None)
        self.user_tier = settings.value(TIER_KEY, None)
        self.user_credits = settings.value(CREDITS_KEY, None)
        # If credits are stored as JSON string, parse into dict
        if isinstance(self.user_credits, str):
            try:
                self.user_credits = json.loads(self.user_credits)
            except Exception:
                logger.debug("Credits not JSON-encoded; keeping original value.")
        settings.endGroup()
        logger.debug(f"Loaded user info: Email={self.user_email}, Tier={self.user_tier}, Credits={self.user_credits}")

    def _save_user_info_to_settings(self):
        """Saves current user information to QSettings."""
        logger.debug(f"Saving user info to settings: Email={self.user_email}, Tier={self.user_tier}, Credits={self.user_credits}")
        settings = QSettings("ComicLabs", "ComicTranslate")
        settings.beginGroup(USER_INFO_GROUP)
        if self.user_email:
            settings.setValue(EMAIL_KEY, self.user_email)
        else:
            settings.remove(EMAIL_KEY)

        if self.user_tier is not None:
             settings.setValue(TIER_KEY, self.user_tier)
        else:
             settings.remove(TIER_KEY)

        if self.user_credits is not None:
             if isinstance(self.user_credits, dict):
                 try:
                     settings.setValue(CREDITS_KEY, json.dumps(self.user_credits))
                 except Exception:
                     logger.warning("Failed to serialize credits dict; storing raw.")
                     settings.setValue(CREDITS_KEY, self.user_credits)
             else:
                 settings.setValue(CREDITS_KEY, self.user_credits)
        else:
             settings.remove(CREDITS_KEY)
        settings.endGroup()
        logger.debug("User info saved.")

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
    
    # Authentication Flow Methods 

    def start_sign_in(self):
        """Initiates the authentication flow."""
        logger.info("Sign In button clicked.")
        # Disable button to prevent multiple clicks
        self.ui.sign_in_button.setEnabled(False)
        self.ui.sign_in_button.setText(self.tr("Signing In..."))
        try:
            self.auth_client.start_auth_flow()
        except Exception as e:
            logger.error(f"Error starting auth flow: {e}", exc_info=True)
            self.handle_auth_error(self.tr("Failed to initiate sign-in process."))
            # Re-enable button on immediate failure
            self.ui.sign_in_button.setEnabled(True)
            self.ui.sign_in_button.setText(self.tr("Sign In"))


    def show_login_view(self, url: str):
        """Creates and shows the QWebEngineView dialog."""
        logger.info(f"Showing login view for URL: {url}")
        # Close existing dialog if any
        if self.login_dialog and self.login_dialog.isVisible():
            # Ensure proper cleanup if replacing an existing dialog
            self.login_dialog.close() # Triggers closeEvent

        # Create and show the new dialog
        self.login_dialog = LoginWebViewDialog(url, self)
        # --- ADDED: Connect finished signal ---
        # Connect finished signal to handle closure regardless of how it happened
        self.login_dialog.finished.connect(self.on_login_dialog_closed)
        self.login_dialog.show()

    def on_login_dialog_closed(self, result_code: int):
        """
        Handle cleanup or state changes when the login dialog is closed.
        result_code is QDialog.Accepted or QDialog.Rejected.
        """
        logger.debug(f"Login dialog closed with result code: {result_code}")
        dialog = self.login_dialog # Keep temporary reference if needed for logging/state
        self.login_dialog = None # Clear the main reference immediately

        # Check if the dialog was closed *without* success (i.e., manually or rejected)
        # AND if the user is not already logged in (auth_success might have just run)
        if result_code != QtWidgets.QDialog.Accepted and not self.is_logged_in():
            logger.info("Login dialog closed without success, cancelling auth flow.")
            # Tell the auth client to stop the local server and cleanup
            self.auth_client.cancel_auth_flow()
            # Note: cancel_auth_flow emits auth_error("cancelled by user..."),
            # which triggers handle_auth_error, resetting the button.
        elif result_code == QtWidgets.QDialog.Accepted:
             logger.debug("Login dialog closed with Accepted code (likely due to auth_success).")
        else: # Dialog closed but user is already logged in (edge case?)
             logger.debug("Login dialog closed, but user is already logged in. No cancellation needed.")
             # Ensure button state is correct if somehow it wasn't updated
             self._update_account_view()

    def open_pricing_page(self):
        """Open the pricing page in the system browser."""
        if not self.is_logged_in():
            QtWidgets.QMessageBox.information(
                self,
                self.tr("Sign In Required"),
                self.tr("Please sign in to purchase or manage credits.")
            )
            return
        pricing_url = f"{FRONTEND_BASE_URL}/pricing?source=desktop"
        if QtGui.QDesktopServices.openUrl(QUrl(pricing_url)):
            self._start_pricing_refresh_watch()
        else:
            QtWidgets.QMessageBox.warning(
                self,
                self.tr("Unable to Open Browser"),
                self.tr("Please open the pricing page in your browser: {url}").format(url=pricing_url),
            )

    def _start_pricing_refresh_watch(self):
        """Poll for updated credits after launching external checkout."""
        if self._pricing_refresh_timer is None:
            self._pricing_refresh_timer = QTimer(self)
            self._pricing_refresh_timer.setInterval(15000)
            self._pricing_refresh_timer.timeout.connect(self._poll_pricing_refresh)

        self._pricing_refresh_attempts = 0
        self._pricing_refresh_baseline = self.user_credits
        self._pricing_refresh_timer.start()

    def _stop_pricing_refresh_watch(self):
        if self._pricing_refresh_timer and self._pricing_refresh_timer.isActive():
            self._pricing_refresh_timer.stop()

    def _poll_pricing_refresh(self):
        self._pricing_refresh_attempts += 1
        self.auth_client.check_session_async()
        if self._pricing_refresh_attempts >= 20:
            self._stop_pricing_refresh_watch()

    def handle_auth_success(self, user_info: dict):
        """Handles successful authentication."""
        logger.info(f"Authentication successful. User info received: {user_info}")
        manual = bool(self.login_dialog)
        # Close the login web view dialog *if it exists and is still visible*
        if self.login_dialog:
            logger.debug("Auth success: Closing login dialog.")
            # Use accept() to ensure the finished signal emits Accepted
            self.login_dialog.accept()
            # self.login_dialog = None # This is now handled in on_login_dialog_closed
        else:
            logger.debug("Auth success: Login dialog was already closed or never opened.")

        # Store user info
        self.user_email = user_info.get('email')
        self.user_tier = user_info.get('tier')
        self.user_credits = user_info.get('credits')
        if self._pricing_refresh_baseline is not None and self.user_credits != self._pricing_refresh_baseline:
            self._stop_pricing_refresh_watch()
            self._pricing_refresh_baseline = None

        # Save user info to QSettings
        self._save_user_info_to_settings()

        # Update the Account page UI
        self._update_account_view()

        # Emit state change signal
        self.login_state_changed.emit(True)

        # Optionally show a success message
        if manual:
            QtWidgets.QMessageBox.information(
                self, 
                self.tr("Success"), 
                self.tr("Successfully signed in as {email}.").format(email=self.user_email)
            )

    def handle_auth_error(self, error_message: str):
        """Handles authentication errors."""
        # REMOVED: if "cancelled by user" not in error_message:
        logger.error(f"Authentication error: {error_message}") # Now always logs as error

        manual = bool(self.login_dialog)
        # Close the login web view dialog *if it exists and is still visible*
        if self.login_dialog:
            logger.debug("Auth error: Closing login dialog.")
            self.login_dialog.reject()
            # self.login_dialog = None # Handled in on_login_dialog_closed
        else:
            logger.debug("Auth error: Login dialog was already closed or never opened.")

        # Update account view should handle showing/hiding widgets and resetting buttons
        self._update_account_view()

        # Show error message to the user
        if manual:
            QtWidgets.QMessageBox.warning(
                self, 
                self.tr("Sign In Error"), 
                self.tr("Authentication failed: {error}").format(error=error_message)
            )

    def handle_auth_cancelled(self):
        """Handles the signal emitted when the auth flow is cancelled by the user."""
        logger.info("Authentication flow cancelled by user.")
        # The login dialog should already be closing or closed by this point.
        # Ensure the UI reflects the logged-out state correctly.
        self._update_account_view()
        # Explicitly ensure sign-in button is reset, although _update_account_view should handle it.
        if not self.is_logged_in():
            self.ui.sign_in_button.setEnabled(True)
            self.ui.sign_in_button.setText(self.tr("Sign In"))

    def sign_out(self):
        """Initiates the sign-out process."""
        logger.info("Sign Out button clicked.")
        # Confirmation dialog
        reply = QtWidgets.QMessageBox.question(
            self, self.tr("Confirm Sign Out"),
            self.tr("Are you sure you want to sign out?"),
            QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No,
            QtWidgets.QMessageBox.No
        )

        if reply == QtWidgets.QMessageBox.Yes:
            self.ui.sign_out_button.setEnabled(False)
            self.ui.sign_out_button.setText(self.tr("Signing Out..."))
            # AuthClient handles token/setting clearing and emits logout_success
            self.auth_client.logout()
        else:
            logger.debug("Sign out cancelled by user.")

    def handle_logout_success(self):
        """Handles successful logout completion from AuthClient."""
        logger.info("Logout successful.")
        self._stop_pricing_refresh_watch()
        self._pricing_refresh_baseline = None
        # Clear local state variables
        self.user_email = None
        self.user_tier = None
        self.user_credits = None

        # Update the Account page UI
        self._update_account_view()

        # Re-enable sign out button (it will be hidden by _update_account_view,
        # but good practice to reset state)
        self.ui.sign_out_button.setEnabled(True)
        self.ui.sign_out_button.setText(self.tr("Sign Out"))

        # Emit state change signal
        self.login_state_changed.emit(False)

        # Optionally show message
        # QtWidgets.QMessageBox.information(self, self.tr("Signed Out"), self.tr("You have been signed out."))

    def handle_session_check_finished(self, is_valid: bool):
        """Handles the result of the background session check."""
        if not is_valid:
            logger.warning("Session check failed (invalid token or refresh failed). Signing out.")
            
            # Alert the user about the expiration
            QtWidgets.QMessageBox.warning(
                self,
                self.tr("Session Expired"),
                self.tr("Your session has expired. Please sign in again.")
            )

            # We can call logout directly. AuthClient.logout() emits logout_success,
            # which updates the UI via handle_logout_success.
            self.auth_client.logout()
        else:
            logger.info("Session check passed.")

    def _update_account_view(self):
        """Updates the UI elements on the Account page based on login state."""
        logger.debug(f"Updating account view. Logged in: {self.is_logged_in()}")
        if self.is_logged_in():
            self.ui.account_page.show_logged_in()
            self.ui.email_value_label.setText(self.user_email or self.tr("N/A"))
            self.ui.tier_value_label.setText(str(self.user_tier) if self.user_tier is not None else self.tr("N/A"))
            # Format credits display (supports dict or legacy int)
            credits_text = self.tr("N/A")
            if isinstance(self.user_credits, dict):
                sub = self.user_credits.get('subscription')
                one = self.user_credits.get('one_time')
                total = self.user_credits.get('total')
                parts = []
                if sub is not None:
                    parts.append(f"{self.tr('Subscription')}: {sub}")
                if one is not None:
                    parts.append(f"{self.tr('One-time')}: {one}")
                if total is not None:
                    parts.append(f"{self.tr('Total')}: {total}")
                if parts:
                    credits_text = " | ".join(parts)
            elif self.user_credits is not None:
                credits_text = f"{self.tr('Total')}: {self.user_credits}"
            self.ui.credits_value_label.setText(credits_text)
            self.ui.buy_credits_button.setEnabled(True)
            self.ui.buy_credits_button.show()
            # Ensure sign out button is enabled when view is shown
            self.ui.sign_out_button.setEnabled(True)
            self.ui.sign_out_button.setText(self.tr("Sign Out"))
        else:
            self.ui.account_page.show_logged_out()
            # Ensure sign in button is enabled when view is shown
            self.ui.buy_credits_button.setEnabled(False)
            self.ui.buy_credits_button.hide()
            self.ui.sign_in_button.setEnabled(True)
            self.ui.sign_in_button.setText(self.tr("Sign In"))

        # Update geometry to recalculate scroll area size after state change
        if hasattr(self.ui, 'content_scroll'):
            self.ui.content_scroll.updateGeometry()

    def is_logged_in(self) -> bool:
        """Checks if user info indicates a logged-in state."""
        return self.auth_client.is_authenticated()
    
    def closeEvent(self, event):
        """Ensure login dialog is closed when the settings page itself closes."""
        logger.debug("SettingsPage closeEvent triggered.")
        if self.login_dialog:
            logger.info("Closing active login dialog because SettingsPage is closing.")
            # Closing the dialog will trigger its finished signal,
            # which calls on_login_dialog_closed, potentially cancelling the auth flow.
            self.login_dialog.close()
        self._stop_pricing_refresh_watch()
        super().closeEvent(event)
    



