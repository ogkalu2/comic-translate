import numpy as np
from typing import Any

from modules.utils.textblock import TextBlock
from modules.utils.language_utils import language_codes, \
    get_lang_code_for_script, get_ocr_bucket_for_script, \
    get_dominant_page_script, is_supported_script, normalize_script
from .factory import OCRFactory


class OCRProcessor:
    """
    Processor for OCR operations using various engines.
    
    Uses a factory pattern to create and utilize the appropriate OCR engine
    based on settings and language.
    """
    
    def __init__(self):
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

        self._set_source_language(blk_list)

        if self.source_lang_english == 'Auto':
            return self._process_auto(img, blk_list)

        engine = OCRFactory.create_engine(self.settings, self.source_lang_english, self.ocr_key)
        return engine.process_image(img, blk_list)

    def _process_auto(self, img: np.ndarray, blk_list: list[TextBlock]) -> list[TextBlock]:
        """Route each block to an OCR engine using block script plus a page-level fallback."""
        dominant_script = self._get_dominant_page_script(blk_list)
        groups: dict[str, list[TextBlock]] = {}
        for blk in blk_list:
            resolved_script = self._resolve_auto_script(blk, dominant_script)
            bucket = get_ocr_bucket_for_script(resolved_script)
            groups.setdefault(bucket, []).append(blk)

        for bucket, blks in groups.items():
            engine = OCRFactory.create_engine(self.settings, bucket, self.ocr_key)
            engine.process_image(img, blks)

        return blk_list

    def _set_source_language(self, blk_list: list[TextBlock]) -> None:
        if self.source_lang_english == 'Auto':
            dominant_script = self._get_dominant_page_script(blk_list)
            for blk in blk_list:
                resolved_script = self._resolve_auto_script(blk, dominant_script)
                blk.source_lang = get_lang_code_for_script(resolved_script)
            return

        source_lang_code = language_codes.get(self.source_lang_english, 'en')
        for blk in blk_list:
            blk.source_lang = source_lang_code

    def _resolve_auto_script(self, blk: TextBlock, dominant_script: str) -> str:
        script = normalize_script(getattr(blk, 'script', ''))
        if is_supported_script(script):
            return script
        return dominant_script or script

    def _get_dominant_page_script(self, blk_list: list[TextBlock]) -> str:
        return get_dominant_page_script(blk_list)

    def _get_ocr_key(self, localized_ocr: str) -> str:
        translator_map = {
            self.settings.ui.tr('GPT-4.1-mini'): 'GPT-4.1-mini',
            self.settings.ui.tr('Microsoft OCR'): 'Microsoft OCR',
            self.settings.ui.tr('Google Cloud Vision'): 'Google Cloud Vision',
            self.settings.ui.tr('Gemini-2.5-Flash-Lite'): 'Gemini-2.5-Flash-Lite',
            self.settings.ui.tr('Default'): 'Default',
        }
        return translator_map.get(localized_ocr, localized_ocr)
