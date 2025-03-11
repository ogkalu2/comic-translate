from typing import Any

from .base import TraditionalTranslation
from ..utils.textblock import TextBlock


class DeepLTranslation(TraditionalTranslation):
    """Translation engine using DeepL API."""
    
    def __init__(self):
        self.source_lang_code = None
        self.target_lang_code = None
        self.api_key = None
        self.translator = None
        self.target_lang = None
        
    def initialize(self, settings: Any, source_lang: str, target_lang: str) -> None:

        import deepl

        self.source_lang_code = self.get_language_code(source_lang)
        self.target_lang_code = self.get_language_code(target_lang)
        self.target_lang = target_lang
        
        credentials = settings.get_credentials(settings.ui.tr("DeepL"))
        self.api_key = credentials.get('api_key', '')
        self.translator = deepl.Translator(self.api_key)
        
    def translate(self, blk_list: list[TextBlock]) -> list[TextBlock]:
        try:
            for blk in blk_list:
                text = self.preprocess_text(blk.text, self.source_lang_code)
                
                if not text.strip():
                    blk.translation = ''
                    continue
                
                # Handle special cases for language codes
                target_code = self.target_lang_code
                if self.target_lang == 'Simplified Chinese':
                    target_code = "zh"
                elif self.target_lang == 'English':
                    target_code = "EN-US"
                
                result = self.translator.translate_text(text, source_lang=self.source_lang_code, target_lang=target_code)
                blk.translation = result.text
        
        except Exception as e:
            print(f"DeepL Translator error: {str(e)}")
            
        return blk_list