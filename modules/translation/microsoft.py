from typing import Any
from deep_translator import MicrosoftTranslator

from .base import TraditionalTranslation
from ..utils.textblock import TextBlock


class MicrosoftTranslation(TraditionalTranslation):
    """Translation engine using Microsoft Translator API."""
    
    def __init__(self):
        self.source_lang_code = None
        self.target_lang_code = None
        self.api_key = None
        self.region = None
        
    def initialize(self, settings: Any, source_lang: str, target_lang: str) -> None:
        self.source_lang_code = self.get_language_code(source_lang)
        self.target_lang_code = self.get_language_code(target_lang)
        
        credentials = settings.get_credentials(settings.ui.tr("Microsoft Azure"))
        self.api_key = credentials['api_key_translator']
        self.region = credentials['region_translator']
        
    def translate(self, blk_list: list[TextBlock]) -> list[TextBlock]:
        try:
            translator = MicrosoftTranslator(
                self.source_lang_code, 
                self.target_lang_code, 
                self.api_key, 
                self.region
            )
            
            for blk in blk_list:
                # Handle Chinese/Japanese spacing appropriately
                text = blk.text.replace(" ", "") if (
                    'zh' in self.source_lang_code.lower() or 
                    self.source_lang_code.lower() == 'ja'
                ) else blk.text
                
                if not text.strip():
                    blk.translation = ""
                    continue
                    
                translation = translator.translate(text)
                if translation is not None:
                    blk.translation = translation
                else:
                    blk.translation = ""
        
        except Exception as e:
            print(f"Microsoft Translator error: {str(e)}")
            
        return blk_list