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


def get_inpainter_backend(inpainter_key: str) -> str:
    inpainter_cls = inpaint_map[inpainter_key]
    return getattr(inpainter_cls, "preferred_backend", "onnx")

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
    """Ensure the OCR tool can run.

    Account/credit-backed cloud tools (Gemini, Microsoft OCR) require the user
    to be signed in. Local tools ('Default') and user-provided endpoints
    ('Custom') run without an account, so they must not be gated behind login.
    """
    settings_page = main.settings_page
    tr = settings_page.ui.tr
    settings = settings_page.get_all_settings()
    ocr_tool = settings['tools']['ocr']

    if not ocr_tool:
        Messages.show_missing_tool_error(main, QCoreApplication.translate("Messages", "Text Recognition model"))
        return False

    # Normalize the (localized) tool name to its internal English key.
    ocr_key = settings_page.ui.value_mappings.get(ocr_tool, ocr_tool)

    # Only account/credit-backed cloud tools require authentication.
    account_backed_ocr = {tr('Gemini-2.5-Flash-Lite'), tr('Microsoft OCR')}
    if ocr_tool in account_backed_ocr:
        if not settings_page.is_logged_in():
            Messages.show_not_logged_in_error(main)
            return False

    # The custom provider uses the user's own endpoint and must be configured.
    if ocr_key == 'Custom':
        creds = settings_page.get_ocr_credentials()
        if not all([creds.get('api_url'), creds.get('model')]):
            Messages.show_custom_not_configured_error(main)
            return False

    return True


def validate_translator(main: ComicTranslate, target_lang: str):
    """Ensure the translator can run.

    The custom translator uses the user's own API (configured in Advanced) and
    must not be gated behind account login. Cloud/account translators require
    the user to be signed in.
    """
    settings_page = main.settings_page
    tr = settings_page.ui.tr
    settings = settings_page.get_all_settings()
    credentials = settings.get('credentials', {})
    translator_tool = settings['tools']['translator']

    if not translator_tool:
        Messages.show_missing_tool_error(main, QCoreApplication.translate("Messages", "Translator"))
        return False

    # Normalize the (localized) tool name to its internal English key.
    translator_key = settings_page.ui.value_mappings.get(translator_tool, translator_tool)

    # The custom translator is configured locally (Advanced > Custom) and does
    # not require an account. Only validate that the credentials are present.
    if translator_key == 'Custom':
        service = tr('Custom')
        creds = credentials.get(service, {})
        if not all([creds.get('api_key'), creds.get('api_url'), creds.get('model')]):
            Messages.show_custom_not_configured_error(main)
            return False
        return True

    # All other translators are account/credit-backed cloud models.
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
