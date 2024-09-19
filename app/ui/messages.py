from .dayu_widgets.message import MMessage
from PySide6.QtCore import QCoreApplication

class Messages:
    @staticmethod
    def show_api_key_translator_error(parent):
        MMessage.error(
            text=QCoreApplication.translate("Messages", "An API Key is required for the selected translator.\nGo to Settings > Credentials to set one"),
            parent=parent,
            duration=None,
            closable=True
        )

    @staticmethod
    def show_api_key_ocr_error(parent):
        MMessage.error(
            text=QCoreApplication.translate("Messages", "An API Key is required for the selected OCR.\nGo to Settings > Credentials to set one"),
            parent=parent,
            duration=None,
            closable=True
        )

    @staticmethod
    def show_api_key_ocr_gpt4v_error(parent):
        MMessage.error(
            text=QCoreApplication.translate("Messages", "Default OCR for one of the selected Source Languages is GPT-4o\nwhich requires an API Key. Go to Settings > Credentials > GPT to set one"),
            parent=parent,
            duration=None,
            closable=True
        )

    @staticmethod
    def show_endpoint_url_error(parent):
        MMessage.error(
            text=QCoreApplication.translate("Messages", "An Endpoint URL is required for Microsoft OCR.\nGo to Settings > Credentials > Microsoft to set one"),
            parent=parent,
            duration=None,
            closable=True
        )

    @staticmethod
    def show_deepl_ch_error(parent):
        MMessage.error(
            text=QCoreApplication.translate("Messages", "DeepL does not translate to Traditional Chinese"),
            parent=parent,
            duration=None,
            closable=True
        )

    @staticmethod
    def show_googlet_ptbr_error(parent):
        MMessage.error(
            text=QCoreApplication.translate("Messages", "Google Translate does not support Brazillian Portuguese"),
            parent=parent,
            duration=None,
            closable=True
        )

    @staticmethod
    def show_deepl_th_error(parent):
        MMessage.error(
            text=QCoreApplication.translate("Messages", "DeepL does not translate to Thai"),
            parent=parent,
            duration=None,
            closable=True
        )

    @staticmethod
    def show_deepl_vi_error(parent):
        MMessage.error(
            text=QCoreApplication.translate("Messages", "DeepL does not translate to Vietnamese"),
            parent=parent,
            duration=None,
            closable=True
        )

    @staticmethod
    def show_translation_complete(parent):
        MMessage.success(
            text=QCoreApplication.translate("Messages", "Comic has been Translated!"),
            parent=parent,
            duration=None,
            closable=True
        )

    @staticmethod
    def select_font_error(parent):
        MMessage.error(
            text=QCoreApplication.translate("Messages", "No Font selected.\nGo to Settings > Text Rendering > Font to select or import one "),
            parent=parent,
            duration=None,
            closable=True
        )
