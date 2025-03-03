from typing import Any
from deep_translator import YandexTranslator

from .base import TextTranslationEngine
from ..utils.textblock import TextBlock


class YandexTranslationEngine(TextTranslationEngine):
    """Translation engine using Yandex Translator API."""
    
    def __init__(self):
        """Initialize Yandex translation engine."""
        self.source_lang_code = None
        self.target_lang_code = None
        self.api_key = None
        
    def initialize(self, settings: Any, source_lang: str, target_lang: str, **kwargs) -> None:
        """
        Initialize Yandex Translator engine.
        
        Args:
            settings: Settings object with credentials
            source_lang: Source language name
            target_lang: Target language name
            **kwargs: Additional parameters (ignored)
        """
        self.source_lang_code = self.get_language_code(source_lang)
        self.target_lang_code = self.get_language_code(target_lang)
        
        credentials = settings.get_credentials(settings.ui.tr("Yandex"))
        self.api_key = credentials['api_key']
        
    def translate(self, blk_list: list[TextBlock]) -> list[TextBlock]:
        """
        Translate text blocks using Yandex Translator.
        
        Args:
            blk_list: List of TextBlock objects to translate
            
        Returns:
            List of updated TextBlock objects with translations
        """
        try:
            translator = YandexTranslator(
                source='auto', 
                target=self.target_lang_code, 
                api_key=self.api_key
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
            print(f"Yandex Translator error: {str(e)}")
            
        return blk_list