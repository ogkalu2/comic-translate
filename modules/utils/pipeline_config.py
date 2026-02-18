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

    if not ocr_tool:
        Messages.show_missing_tool_error(main, QCoreApplication.translate("Messages", "Text Recognition model"))
        return False
    
    # 'Default' model is fully local (Manga-OCR, Pororo, PPOCRv5) - no authentication needed
    if ocr_tool == 'Default':
        return True
    
    # For cloud-based OCR models, authentication is required
    if not settings_page.is_logged_in():
        Messages.show_not_logged_in_error(main)
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

    # 'Ollama' is fully local (runs on localhost:11434) - no authentication needed
    if translator_tool == 'Ollama':
        return True
    
    # 'Custom' translator requires local API credentials but not account authentication
    if "Custom" in translator_tool:
        # Custom requires api_key, api_url, and model to be configured LOCALLY
        service = tr('Custom')
        creds = credentials.get(service, {})
        # Check if all required fields are present and non-empty
        if not all([creds.get('api_key'), creds.get('api_url'), creds.get('model')]):
            Messages.show_custom_not_configured_error(main)
            return False
        return True
    
    # For cloud-based translators (GPT, Claude, DeepL, etc.), authentication is required
    if not settings_page.is_logged_in():
        Messages.show_not_logged_in_error(main)
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
