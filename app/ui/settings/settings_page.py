import os, shutil
import socket
from typing import Any, Optional
import logging
from dataclasses import asdict, is_dataclass
import json

from PySide6 import QtWidgets, QtGui
from PySide6.QtCore import Signal, QSettings, QUrl, QTimer, Qt
from PySide6.QtGui import QFont, QFontDatabase, QDesktopServices

from .settings_ui import SettingsPageUI
from modules.utils.device import is_gpu_available
from app.account.auth.auth_client import AuthClient, USER_INFO_GROUP, \
    EMAIL_KEY, TIER_KEY, CREDITS_KEY, MONTHLY_CREDITS_KEY
from app.account.config import API_BASE_URL, FRONTEND_BASE_URL
from app.update_checker import UpdateChecker
from modules.utils.paths import get_user_data_dir


logger = logging.getLogger(__name__)


class SettingsPage(QtWidgets.QWidget):
    theme_changed = Signal(str)
    font_imported = Signal(str)
    login_state_changed = Signal(bool)

    def __init__(self, parent=None):
        super(SettingsPage, self).__init__(parent)

        self.ui = SettingsPageUI(self)
        self._setup_connections()
        self._loading_settings = False
        self._is_background_check = False
        self._current_language = None  # Track current language for revert

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

        # Update Checker
        self.update_checker = UpdateChecker()
        self.update_checker.update_available.connect(self.on_update_available)
        self.update_checker.up_to_date.connect(self.on_up_to_date)
        self.update_checker.error_occurred.connect(self.on_update_error)
        self.update_checker.download_progress.connect(self.on_download_progress)
        self.update_checker.download_finished.connect(self.on_download_finished)
        self.update_dialog = None
        self.login_dialog = None


        self.user_email: Optional[str] = None
        self.user_tier: Optional[str] = None
        self.user_credits: Optional[Any] = None
        self.user_monthly_credits: Optional[int] = None

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
        # Avoid blocking the UI thread with network calls and avoid duplicating
        # `check_session_async()` (which already validates + refreshes user info).
        if self._is_online() and self.auth_client.is_authenticated():
            self.auth_client.check_session_async()

    def _setup_connections(self):
        # Connect signals to slots
        self.ui.theme_combo.currentTextChanged.connect(self.on_theme_changed)
        self.ui.lang_combo.currentTextChanged.connect(self.on_language_changed)
        self.ui.translator_combo.currentTextChanged.connect(self.on_translator_changed)
        self.ui.ocr_combo.currentTextChanged.connect(self.on_ocr_changed)
        self.ui.font_browser.sig_files_changed.connect(self.import_font)
        self.ui.sign_in_button.clicked.connect(self.start_sign_in)
        self.ui.buy_credits_button.clicked.connect(self.open_pricing_page)
        self.ui.sign_out_button.clicked.connect(self.sign_out)
        self.ui.check_update_button.clicked.connect(self.check_for_updates)

    def on_theme_changed(self, theme: str):
        self.theme_changed.emit(theme)
    
    def on_translator_changed(self, translator: str):
        """Clear all engine caches when translator selection changes."""
        from modules.translation.factory import TranslationFactory
        from modules.ocr.factory import OCRFactory
        TranslationFactory.clear_cache()
        OCRFactory.clear_cache()
    
    def on_ocr_changed(self, ocr_engine: str):
        """Clear OCR engine cache when OCR selection changes."""
        from modules.ocr.factory import OCRFactory
        OCRFactory.clear_cache()

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
        if not is_gpu_available():
            return False
        return self.ui.use_gpu_checkbox.isChecked()

    def get_llm_settings(self):
        return {
            'extra_context': self.ui.extra_context.toPlainText(),
            'image_input_enabled': self.ui.image_checkbox.isChecked(),
        }

    def get_export_settings(self):
        settings = {
            'auto_save': self.ui.auto_save_checkbox.isChecked(),
            'export_raw_text': self.ui.raw_text_checkbox.isChecked(),
            'export_translated_text': self.ui.translated_text_checkbox.isChecked(),
            'export_inpainted_image': self.ui.inpainted_image_checkbox.isChecked(),
            'archive_save_as': self.ui.archive_save_as_combo.currentText(),
        }
        return settings

    def get_credentials(self, service: str = ""):
        save_keys = self.ui.save_keys_checkbox.isChecked()

        def _text_or_none(widget_key):
            w = self.ui.credential_widgets.get(widget_key)
            return w.text() if w is not None else None

        if service:
            normalized = self.ui.value_mappings.get(service, service)
            creds = {'save_key': save_keys}
            if normalized == "Ollama":
                for field in ("model", "api_url", "api_key"):
                    creds[field] = _text_or_none(f"Ollama_{field}")
            elif normalized == "Custom":
                for field in ("api_key", "api_url", "model"):
                    creds[field] = _text_or_none(f"Custom_{field}")

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
            'credits': self.user_credits,
            'monthly_credits': self.user_monthly_credits
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
                      if f.lower().endswith((".ttf", ".ttc", ".otf", ".woff", ".woff2"))]
        
        # Determine user font directory
        user_font_dir = os.path.join(get_user_data_dir(), "fonts")

        if not os.path.exists(user_font_dir):
            os.makedirs(user_font_dir, exist_ok=True)

        if file_paths:
            for file in file_paths:
                shutil.copy(file, user_font_dir)
                
            # Reload fonts from user directory
            font_files = [os.path.join(user_font_dir, f) for f in os.listdir(user_font_dir) 
                      if f.lower().endswith((".ttf", ".ttc", ".otf", ".woff", ".woff2"))]
            
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
                
                if translated_service == "Custom":
                    settings.setValue(f"{translated_service}_api_key", cred['api_key'])
                    settings.setValue(f"{translated_service}_api_url", cred['api_url'])
                    settings.setValue(f"{translated_service}_model", cred['model'])
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
        translator = settings.value('translator', 'Gemini-3.0-Flash')
        translated_translator = self.ui.reverse_mappings.get(translator, translator)
        if self.ui.translator_combo.findText(translated_translator) != -1:
            self.ui.translator_combo.setCurrentText(translated_translator)
        else:
            self.ui.translator_combo.setCurrentIndex(-1)

        ocr = settings.value('ocr', 'Default')
        translated_ocr = self.ui.reverse_mappings.get(ocr, ocr)
        if self.ui.ocr_combo.findText(translated_ocr) != -1:
            self.ui.ocr_combo.setCurrentText(translated_ocr)
        else:
            self.ui.ocr_combo.setCurrentIndex(-1)

        inpainter = settings.value('inpainter', 'AOT')
        translated_inpainter = self.ui.reverse_mappings.get(inpainter, inpainter)
        if self.ui.inpainter_combo.findText(translated_inpainter) != -1:
            self.ui.inpainter_combo.setCurrentText(translated_inpainter)
        else:
            self.ui.inpainter_combo.setCurrentIndex(-1)

        detector = settings.value('detector', 'RT-DETR-v2')
        translated_detector = self.ui.reverse_mappings.get(detector, detector)
        if self.ui.detector_combo.findText(translated_detector) != -1:
            self.ui.detector_combo.setCurrentText(translated_detector)
        else:
            self.ui.detector_combo.setCurrentIndex(-1)

        if is_gpu_available():
            self.ui.use_gpu_checkbox.setChecked(settings.value('use_gpu', False, type=bool))
        else:
             self.ui.use_gpu_checkbox.setChecked(False)

        # Load HD strategy settings
        settings.beginGroup('hd_strategy')
        strategy = settings.value('strategy', 'Resize')
        translated_strategy = self.ui.reverse_mappings.get(strategy, strategy)
        if self.ui.inpaint_strategy_combo.findText(translated_strategy) != -1:
            self.ui.inpaint_strategy_combo.setCurrentText(translated_strategy)
        else:
            self.ui.inpaint_strategy_combo.setCurrentIndex(0)

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
        settings.endGroup()

        # Load export settings
        settings.beginGroup('export')
        self.ui.auto_save_checkbox.setChecked(settings.value('auto_save', True, type=bool))
        self.ui.raw_text_checkbox.setChecked(settings.value('export_raw_text', False, type=bool))
        self.ui.translated_text_checkbox.setChecked(settings.value('export_translated_text', False, type=bool))
        self.ui.inpainted_image_checkbox.setChecked(settings.value('export_inpainted_image', False, type=bool))

        # New: single global archive output format
        archive_save_as = settings.value('archive_save_as', 'zip')
        self.ui.archive_save_as_combo.setCurrentText(str(archive_save_as))

        settings.endGroup()  # export

        # Load credentials
        settings.beginGroup('credentials')
        save_keys = settings.value('save_keys', False, type=bool)
        self.ui.save_keys_checkbox.setChecked(save_keys)
        if save_keys:
            for service in self.ui.credential_services:
                translated_service = self.ui.value_mappings.get(service, service)
                
                if translated_service == "Custom":
                    self.ui.credential_widgets[f"{translated_service}_api_key"].setText(settings.value(f"{translated_service}_api_key", ''))
                    self.ui.credential_widgets[f"{translated_service}_api_url"].setText(settings.value(f"{translated_service}_api_url", ''))
                    self.ui.credential_widgets[f"{translated_service}_model"].setText(settings.value(f"{translated_service}_model", ''))
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

        # Initialize current language tracker after loading
        self._current_language = self.ui.lang_combo.currentText()

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
        self.user_monthly_credits = settings.value(MONTHLY_CREDITS_KEY, None)
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

        if self.user_monthly_credits is not None:
             settings.setValue(MONTHLY_CREDITS_KEY, self.user_monthly_credits)
        else:
             settings.remove(MONTHLY_CREDITS_KEY)

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
            # Pass the previous language so we can revert if needed
            self.show_restart_dialog(new_language)

    def _show_message_box(self, icon: QtWidgets.QMessageBox.Icon, title: str, text: str):
        msg_box = QtWidgets.QMessageBox(self)
        msg_box.setIcon(icon)
        msg_box.setWindowTitle(title)
        msg_box.setText(text)
        ok_btn = msg_box.addButton(self.tr("OK"), QtWidgets.QMessageBox.ButtonRole.AcceptRole)
        msg_box.setDefaultButton(ok_btn)
        msg_box.exec()

    def _ask_yes_no(self, title: str, text: str, default_yes: bool = False) -> bool:
        msg_box = QtWidgets.QMessageBox(self)
        msg_box.setIcon(QtWidgets.QMessageBox.Icon.Question)
        msg_box.setWindowTitle(title)
        msg_box.setText(text)
        yes_btn = msg_box.addButton(self.tr("Yes"), QtWidgets.QMessageBox.ButtonRole.AcceptRole)
        no_btn = msg_box.addButton(self.tr("No"), QtWidgets.QMessageBox.ButtonRole.RejectRole)
        msg_box.setDefaultButton(yes_btn if default_yes else no_btn)
        msg_box.exec()
        return msg_box.clickedButton() == yes_btn

    def show_restart_dialog(self, new_language):
        from modules.utils.common_utils import restart_application
        
        response = self._ask_yes_no(
            self.tr("Restart Required"),
            self.tr("The application needs to restart for the language changes to take effect.\nRestart now?"),
            default_yes=True
        )
        
        if response:
            # Save settings before restarting
            self.save_settings()
            self._current_language = new_language  # Update tracking
            restart_application()
        else:
            # User declined - revert to previous language
            self._loading_settings = True  # Prevent triggering the handler again
            self.ui.lang_combo.setCurrentText(self._current_language)
            self._loading_settings = False



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

    # Authentication Flow Methods 

    def start_sign_in(self):
        """Initiates the authentication flow."""
        logger.info("Sign In button clicked.")
        # Change button to Cancel mode
        self.ui.sign_in_button.setText(self.tr("Cancel"))
        self.ui.sign_in_button.clicked.disconnect()
        self.ui.sign_in_button.clicked.connect(self.cancel_sign_in)
        
        try:
            self.auth_client.start_auth_flow()
        except Exception as e:
            logger.error(f"Error starting auth flow: {e}", exc_info=True)
            self.handle_auth_error(self.tr("Failed to initiate sign-in process."))
            # handle_auth_error will reset the button

    def cancel_sign_in(self):
        """Cancels the active authentication flow."""
        logger.info("Cancel Sign In button clicked.")
        self.auth_client.cancel_auth_flow()
        # The auth_client will emit auth_cancelled(), which calls handle_auth_cancelled()
        # handle_auth_cancelled will reset the button

    def show_login_view(self, url: str):
        """Opens the login URL in the system browser."""
        logger.info(f"Opening login URL in system browser: {url}")
        QDesktopServices.openUrl(QUrl(url))

    def _reset_sign_in_button(self):
        """Resets the Sign In button to its initial state."""
        self.ui.sign_in_button.setText(self.tr("Sign In"))
        self.ui.sign_in_button.setEnabled(True)
        try:
            self.ui.sign_in_button.clicked.disconnect()
        except RuntimeError:
            pass # No connections to disconnect
        self.ui.sign_in_button.clicked.connect(self.start_sign_in)

    def _on_auth_flow_ended(self):
        """Common cleanup when auth flow ends (success, error, or cancel)."""
        self._reset_sign_in_button()

    def open_pricing_page(self):
        """Open the pricing page in the system browser."""
        if not self.is_logged_in():
            self._show_message_box(
                QtWidgets.QMessageBox.Information,
                self.tr("Sign In Required"),
                self.tr("Please sign in to purchase or manage credits.")
            )
            return
        pricing_url = f"{FRONTEND_BASE_URL}/pricing/?source=desktop"
        if QtGui.QDesktopServices.openUrl(QUrl(pricing_url)):
            self._start_pricing_refresh_watch()
        else:
            self._show_message_box(
                QtWidgets.QMessageBox.Warning,
                self.tr("Unable to Open Browser"),
                self.tr("Please open the pricing page in your browser: {url}").format(url=pricing_url)
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
        # logger.info(f"Authentication successful. User info received: {user_info}")
        
        self._on_auth_flow_ended()
        
        logger.debug("Auth success: Flow completed.")

        # Store user info
        self.user_email = user_info.get('email')
        self.user_tier = user_info.get('tier')
        self.user_credits = user_info.get('credits')
        self.user_monthly_credits = user_info.get('monthly_credits')
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
        # if self.user_email: 
        #     self._show_message_box(
        #         QtWidgets.QMessageBox.Information,
        #         self.tr("Success"),
        #         self.tr("Successfully signed in as {email}.").format(email=self.user_email)
        #     )

    def handle_auth_error(self, error_message: str):
        """Handles authentication errors."""
        # REMOVED: if "cancelled by user" not in error_message:
        logger.error(f"Authentication error: {error_message}") # Now always logs as error

        self._on_auth_flow_ended()

        # Update account view should handle showing/hiding widgets and resetting buttons
        self._update_account_view()

        # Show error message to the user
        if "cancelled" not in error_message.lower():
            self._show_message_box(
                QtWidgets.QMessageBox.Warning,
                self.tr("Sign In Error"),
                self.tr("Authentication failed: {error}").format(error=error_message)
            )

    def handle_auth_cancelled(self):
        """Handles the signal emitted when the auth flow is cancelled by the user."""
        logger.info("Authentication flow cancelled by user.")
        self._on_auth_flow_ended()
        self._update_account_view()

    def sign_out(self):
        """Initiates the sign-out process."""
        logger.info("Sign Out button clicked.")
        # Confirmation dialog
        if self._ask_yes_no(
            self.tr("Confirm Sign Out"),
            self.tr("Are you sure you want to sign out?"),
            default_yes=False
        ):
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
        self.user_monthly_credits = None

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
            self._show_message_box(
                QtWidgets.QMessageBox.Icon.Warning,
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
            
            # Format tier display to show credits/month if available
            tier_display = str(self.user_tier) if self.user_tier is not None else self.tr("N/A")
            
            try:
                monthly = int(self.user_monthly_credits or 0)
                if monthly > 0:
                    if monthly >= 1000 and monthly % 1000 == 0:
                        tier_display = f"{monthly // 1000}k {self.tr('credits/month')}"
                    else:
                        tier_display = f"{monthly:,} {self.tr('credits/month')}"
                else:
                    # If 0 or None, default to "Free" to match site behavior
                    tier_display = self.tr("Free")
            except (ValueError, TypeError):
                # Fallback to existing tier name if parsing fails
                pass
            
            self.ui.tier_value_label.setText(tier_display)
            
            # Format credits display (supports dict or legacy int)
            credits_text = self.tr("N/A")
            if isinstance(self.user_credits, dict):
                sub = self.user_credits.get('subscription')
                one = self.user_credits.get('one_time')
                total = self.user_credits.get('total')
                parts = []
                if sub is not None:
                    label = self.tr('Subscription')
                    parts.append(f"{label}: {sub}")
                if one is not None:
                    label = self.tr('One-time')
                    parts.append(f"{label}: {one}")
                if total is not None:
                    label = self.tr('Total')
                    parts.append(f"{label}: {total}")
                if parts:
                    credits_text = " | ".join(parts)
            elif self.user_credits is not None:
                label = self.tr('Total')
                credits_text = f"{label}: {self.user_credits}"
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
    
    
    def check_for_updates(self, is_background=False):
        self._is_background_check = is_background
        if not is_background:
            self.ui.check_update_button.setEnabled(False)
            self.ui.check_update_button.setText(self.tr("Checking..."))
        self.update_checker.check_for_updates()

    def on_update_available(self, version, release_url, download_url):
        if not self._is_background_check:
            self.ui.check_update_button.setEnabled(True)
            self.ui.check_update_button.setText(self.tr("Check for Updates"))
        
        # Check ignored version
        settings = QSettings("ComicLabs", "ComicTranslate")
        ignored_version = settings.value("updates/ignored_version", "")
        
        if self._is_background_check and version == ignored_version:
            return

        msg_box = QtWidgets.QMessageBox(self)
        msg_box.setWindowTitle(self.tr("Update Available"))
        msg_box.setTextFormat(Qt.RichText)
        msg_box.setTextInteractionFlags(Qt.TextBrowserInteraction)
        msg_box.setText(self.tr("A new version {version} is available.").format(version=version))
        link_text = self.tr("Release Notes")
        msg_box.setInformativeText(f'<a href="{release_url}" style="color: #4da6ff;">{link_text}</a>')
        
        download_btn = msg_box.addButton(self.tr("Yes"), QtWidgets.QMessageBox.ButtonRole.AcceptRole)
        cancel_btn = msg_box.addButton(self.tr("No"), QtWidgets.QMessageBox.ButtonRole.RejectRole)
        
        dotted_ask_btn = None
        if self._is_background_check:
            dotted_ask_btn = msg_box.addButton(self.tr("Skip This Version"), QtWidgets.QMessageBox.ButtonRole.ApplyRole)
        
        msg_box.setDefaultButton(download_btn)
        msg_box.exec()

        if msg_box.clickedButton() == download_btn:
            self.start_download(download_url)
        elif dotted_ask_btn and msg_box.clickedButton() == dotted_ask_btn:
            settings.setValue("updates/ignored_version", version)
    
    def on_up_to_date(self):
        if self._is_background_check:
            return

        self.ui.check_update_button.setEnabled(True)
        self.ui.check_update_button.setText(self.tr("Check for Updates"))
        self._show_message_box(
            QtWidgets.QMessageBox.Icon.Information,
            self.tr("Up to Date"),
            self.tr("You are using the latest version.")
        )

    def on_update_error(self, message):
        if self._is_background_check:
            logger.error(f"Background update check failed: {message}")
            return

        self.ui.check_update_button.setEnabled(True)
        self.ui.check_update_button.setText(self.tr("Check for Updates"))
        if self.update_dialog:
             self.update_dialog.close()
        
        self._show_message_box(
            QtWidgets.QMessageBox.Icon.Warning,
            self.tr("Update Error"),
            message
        )

    def start_download(self, url):
        # Create a progress dialog
        self.update_dialog = QtWidgets.QProgressDialog(self.tr("Downloading update..."), self.tr("Cancel"), 0, 100, self)
        self.update_dialog.setWindowModality(Qt.WindowModality.WindowModal)
        self.update_dialog.show()
        
        filename = url.split("/")[-1]
        self.update_checker.download_installer(url, filename)

    def on_download_progress(self, percent):
        if self.update_dialog:
             self.update_dialog.setValue(percent)

    def on_download_finished(self, file_path):
        if self.update_dialog:
             self.update_dialog.close()
        
        # Ask to install
        if self._ask_yes_no(
            self.tr("Download Complete"),
            self.tr("Installer downloaded to {path}. Run it now?").format(path=file_path),
            default_yes=True
        ):
             self.update_checker.run_installer(file_path)

    def closeEvent(self, event):
        """Ensure login dialog is closed when the settings page itself closes."""
        logger.debug("SettingsPage closeEvent triggered.")
        if self.login_dialog:
            logger.info("Closing active login dialog because SettingsPage is closing.")
            # Closing the dialog will trigger its finished signal,
            # which calls on_login_dialog_closed, potentially cancelling the auth flow.
            # self.login_dialog.close() 
            pass
        super().closeEvent(event)

    def shutdown(self):
        """Cleanup resources before app exit."""
        if getattr(self, "_is_shutting_down", False):
            return
        self._is_shutting_down = True

        self._stop_pricing_refresh_watch()

        try:
            self.update_checker.shutdown()
        except Exception:
            pass

        try:
            if self.auth_client:
                self.auth_client.shutdown()
        except Exception:
            pass

        dialog = getattr(self, "login_dialog", None)
        if dialog:
            try:
                dialog.close()
            except Exception:
                pass
    



