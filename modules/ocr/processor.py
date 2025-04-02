import numpy as np
from typing import Any

from ..utils.textblock import TextBlock
from ..utils.pipeline_utils import language_codes
from .factory import OCREngineFactory


class OCRProcessor:
    """
    Processor for OCR operations using various engines.
    
    Uses a factory pattern to create and utilize the appropriate OCR engine
    based on settings and language.
    """
    
    def __init__(self):
        """Initialize OCR processor."""
        self.main_page = None
        self.settings = None
        self.source_lang = None
        self.source_lang_english = None
        
    def initialize(self, main_page: Any, source_lang: str) -> None:
        """
        Initialize the OCR processor with settings and language.
        
        Args:
            main_page: The main application page with settings
            source_lang: The source language for OCR
        """
        self.main_page = main_page
        self.settings = main_page.settings_page
        self.source_lang = source_lang
        self.source_lang_english = self._get_english_lang(source_lang)
        self.ocr_key = self._get_ocr_key(self.settings.get_tool_selection('ocr'))
        
    def _get_english_lang(self, translated_lang: str) -> str:
        return self.main_page.lang_mapping.get(translated_lang, translated_lang)

    def process(self, img: np.ndarray, blk_list: list[TextBlock]) -> list[TextBlock]:
        """
        Process image with appropriate OCR engine.
        
        Args:
            img: Input image as numpy array
            blk_list: List of TextBlock objects to update with OCR text
            
        Returns:
            Updated list of TextBlock objects with recognized text
        """
        # Set language code for each text block
        self._set_source_language(blk_list)
        
        try:
            # Get appropriate OCR engine from factory
            engine = OCREngineFactory.create_engine(self.settings, self.source_lang_english, self.ocr_key)
            
            # Process image with selected engine
            return engine.process_image(img, blk_list)
        
        except Exception as e:
            print(f"OCR processing error: {str(e)}")
            return blk_list
            
    def _set_source_language(self, blk_list: list[TextBlock]) -> None:
        source_lang_code = language_codes.get(self.source_lang_english, 'en')
        for blk in blk_list:
            blk.source_lang = source_lang_code

    def _get_ocr_key(self, localized_ocr: str) -> str:
        translator_map = {
            self.settings.ui.tr("GPT-4o"): "GPT-4o",
            self.settings.ui.tr("Microsoft OCR"): "Microsoft OCR",
            self.settings.ui.tr("Google Cloud Vision"): "Google Cloud Vision",
        }
        return translator_map.get(localized_ocr, localized_ocr)