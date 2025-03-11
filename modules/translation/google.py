from typing import Any
from deep_translator import GoogleTranslator

from .base import TraditionalTranslation
from ..utils.textblock import TextBlock


class GoogleTranslation(TraditionalTranslation):
    """Translation engine using Google Translate."""
    
    def __init__(self):
        self.source_lang_code = None
        self.target_lang_code = None
        
    def initialize(self, settings: Any, source_lang: str, target_lang: str) -> None:
        """
        Initialize Google Translate engine.
        
        Args:
            settings: Settings object with credentials (ignored)
            source_lang: Source language name
            target_lang: Target language name
        """
        self.source_lang_code = self.get_language_code(source_lang)
        self.target_lang_code = self.get_language_code(target_lang)
        
    def translate(self, blk_list: list[TextBlock]) -> list[TextBlock]:
        try:
            translator = GoogleTranslator(source='auto', target=self.target_lang_code)
            
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
            print(f"Google Translate error: {str(e)}")
            
        return blk_list