from __future__ import annotations

from PySide6.QtCore import QCoreApplication
from typing import TYPE_CHECKING
from modules.inpainting.lama import LaMa
from modules.inpainting.mi_gan import MIGAN
from modules.inpainting.aot import AOT
from modules.inpainting.schema import Config
from app.ui.messages import Messages
from app.ui.settings.settings_page import SettingsPage

if TYPE_CHECKING:
    from controller import ComicTranslate

inpaint_map = {
    "LaMa": LaMa,
    "MI-GAN": MIGAN,
    "AOT": AOT,
}

def get_config(settings_page: SettingsPage):
    strategy_settings = settings_page.get_hd_strategy_settings()
    if strategy_settings['strategy'] == settings_page.ui.tr("Resize"):
        config = Config(hd_strategy="Resize", hd_strategy_resize_limit = strategy_settings['resize_limit'])
    elif strategy_settings['strategy'] == settings_page.ui.tr("Crop"):
        config = Config(hd_strategy="Crop", hd_strategy_crop_margin = strategy_settings['crop_margin'],
                        hd_strategy_crop_trigger_size = strategy_settings['crop_trigger_size'])
    else:
        config = Config(hd_strategy="Original")

    return config

def validate_ocr(main: ComicTranslate):
    """Ensure either API credentials are set or the user is authenticated."""
    settings_page = main.settings_page
    tr = settings_page.ui.tr
    settings = settings_page.get_all_settings()
    credentials = settings.get('credentials', {})
    ocr_tool = settings['tools']['ocr']

    # Helper to check authentication or credential
    def has_access(service, key_field):
        return settings_page.is_logged_in() or bool(credentials.get(service, {}).get(key_field))

    # Helper to check authentication or presence of multiple credential fields
    def has_all_credentials(service, keys):
        if settings_page.is_logged_in():
            return True
        creds = credentials.get(service, {})
        return all(creds.get(k) for k in keys)

    if not ocr_tool:
        Messages.show_missing_tool_error(main, QCoreApplication.translate("Messages", "Text Recognition model"))
        return False

    # Microsoft OCR: needs api_key_ocr and endpoint
    if ocr_tool == tr("Microsoft OCR"):
        service = tr("Microsoft Azure")
        if not has_all_credentials(service, ['api_key_ocr', 'endpoint']):
            Messages.show_signup_or_credentials_error(main)
            return False

    # Google Cloud Vision
    elif ocr_tool == tr("Google Cloud Vision"):
        service = tr("Google Cloud")
        if not has_access(service, 'api_key'):
            Messages.show_signup_or_credentials_error(main)
            return False

    # GPT-based OCR
    elif ocr_tool == tr('GPT-4.1-mini'):
        service = tr('Open AI GPT')
        if not has_access(service, 'api_key'):
            Messages.show_signup_or_credentials_error(main)
            return False

    return True


def validate_translator(main: ComicTranslate, target_lang: str):
    """Ensure either API credentials are set or the user is authenticated, plus check compatibility."""
    settings_page = main.settings_page
    tr = settings_page.ui.tr
    settings = settings_page.get_all_settings()
    credentials = settings.get('credentials', {})
    translator_tool = settings['tools']['translator']

    if not translator_tool:
        Messages.show_missing_tool_error(main, QCoreApplication.translate("Messages", "Translator"))
        return False

    def has_access(service, key_field):
        return settings_page.is_logged_in() or bool(credentials.get(service, {}).get(key_field))

    # Credential checks
    if translator_tool == tr("DeepL"):
        service = tr("DeepL")
        if not has_access(service, 'api_key'):
            Messages.show_signup_or_credentials_error(main)
            return False
        
    elif translator_tool == tr("Microsoft Translator"):
        service = tr("Microsoft Azure")
        if not has_access(service, 'api_key_translator'):
            Messages.show_signup_or_credentials_error(main)
            return False
        
    elif translator_tool == tr("Yandex"):
        service = tr("Yandex")
        if not has_access(service, 'api_key'):
            Messages.show_signup_or_credentials_error(main)
            return False
        
    elif "GPT" in translator_tool:
        service = tr('Open AI GPT')
        if not has_access(service, 'api_key'):
            Messages.show_signup_or_credentials_error(main)
            return False
        
    elif "Gemini" in translator_tool:
        service = tr('Google Gemini')
        if not has_access(service, 'api_key'):
            Messages.show_signup_or_credentials_error(main)
            return False
        
    elif "Claude" in translator_tool:
        service = tr('Anthropic Claude')
        if not has_access(service, 'api_key'):
            Messages.show_signup_or_credentials_error(main)
            return False
    
    elif "Custom" in translator_tool:
        # Custom requires api_key, api_url, and model to be configured
        service = tr('Custom')
        creds = credentials.get(service, {})
        # Check if all required fields are present and non-empty
        if not all([creds.get('api_key'), creds.get('api_url'), creds.get('model')]):
            Messages.show_custom_not_configured_error(main)
            return False

    # Unsupported target languages by service
    unsupported = {
        tr("DeepL"): [
            main.tr('Thai'),
        ],
    }
    unsupported_langs = unsupported.get(translator_tool, [])
    if tr(target_lang) in unsupported_langs:
        Messages.show_translator_language_not_supported(main)
        return False

    return True

def font_selected(main: ComicTranslate):
    if not main.render_settings().font_family:
        Messages.select_font_error(main)
        return False
    return True

def validate_settings(main: ComicTranslate, target_lang: str):
    if not validate_ocr(main):
        return False
    if not validate_translator(main, target_lang):
        return False
    if not font_selected(main):
        return False
    
    return True
