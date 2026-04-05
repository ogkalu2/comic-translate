import re
import numpy as np
from typing import Any

from ..utils.textblock import TextBlock
from .crop_utils import extract_block_crops
from .base import OCREngine
from ..utils.language_utils import language_codes
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

    @staticmethod
    def _limit_repeated_letters(text: str, max_repeat: int = 2) -> str:
        if not text:
            return ""

        limited_chars: list[str] = []
        last_char = ""
        repeat_count = 0

        for char in text:
            if char == last_char and char.isalpha():
                repeat_count += 1
            else:
                last_char = char
                repeat_count = 1

            if not char.isalpha() or repeat_count <= max_repeat:
                limited_chars.append(char)

        return "".join(limited_chars)

    @staticmethod
    def sanitize_ocr_text(text: str) -> str:
        if not text:
            return ""
        quote_chars = "\"'`‘’‚‛“”„‟«»‹›〝〞＂＇`´"
        cleaned = text.translate(str.maketrans("", "", quote_chars))
        cleaned = cleaned.replace("…", "")
        cleaned = re.sub(r"\.{2,}", "", cleaned)
        cleaned = " ".join(cleaned.split())
        cleaned = cleaned.strip()
        cleaned = OCRProcessor._limit_repeated_letters(cleaned, max_repeat=2)
        if cleaned.isupper():
            cleaned = cleaned.lower()
        return cleaned

    @classmethod
    def sanitize_block_texts(cls, blk_list: list[TextBlock]) -> list[TextBlock]:
        for blk in blk_list:
            blk.text = cls.sanitize_ocr_text(getattr(blk, "text", ""))
            texts = getattr(blk, "texts", None)
            if texts is not None:
                blk.texts = [
                    sanitized
                    for sanitized in (cls.sanitize_ocr_text(text) for text in texts)
                    if sanitized
                ]
        return blk_list

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
        engine = self.get_engine()
        return self.sanitize_block_texts(engine.process_image(img, blk_list))

    def get_engine(self) -> OCREngine:
        return OCRFactory.create_engine(
            self.settings,
            self.source_lang_english,
            self.ocr_key,
        )

    def process_crops(
        self,
        crops: list[np.ndarray],
        batch_size: int | None = None,
    ) -> tuple[list[str], list[float]]:
        engine = self.get_engine()
        effective_batch_size = batch_size
        if effective_batch_size is None and self.settings is not None:
            effective_batch_size = self.settings.get_batch_settings().get("ocr_batch_size")
        texts, confs = engine.process_crops(crops, batch_size=effective_batch_size)
        return [self.sanitize_ocr_text(text) for text in texts], confs

    def process_page_block_batches(
        self,
        pages: list[tuple[np.ndarray, list[TextBlock], str]],
        batch_size: int | None = None,
        main_page: Any | None = None,
    ) -> list[list[TextBlock]]:
        if not pages:
            return []

        if main_page is not None:
            self.main_page = main_page
            self.settings = main_page.settings_page
        if self.main_page is None or self.settings is None:
            raise RuntimeError("OCRProcessor must be initialized with main_page before batched OCR.")

        results: list[list[TextBlock] | None] = [None] * len(pages)
        grouped: dict[str, list[tuple[int, np.ndarray, list[TextBlock]]]] = {}
        for page_index, (image, blk_list, source_lang) in enumerate(pages):
            grouped.setdefault(source_lang, []).append((page_index, image, blk_list))

        effective_batch_size = batch_size
        if effective_batch_size is None and self.settings is not None:
            effective_batch_size = self.settings.get_batch_settings().get("ocr_batch_size")

        for source_lang, group_items in grouped.items():
            self.initialize(self.main_page, source_lang)
            engine = self.get_engine()

            for _, _, blk_list in group_items:
                self._set_source_language(blk_list)

            if engine.supports_block_crop_batching():
                crop_records: list[tuple[int, int, np.ndarray]] = []
                for page_index, image, blk_list in group_items:
                    crops, invalid_indices = extract_block_crops(
                        image,
                        blk_list,
                        expansion_percentage=getattr(engine, "expansion_percentage", 5),
                    )
                    for block_index in invalid_indices:
                        blk_list[block_index].text = ""
                    for crop_record in crops:
                        crop_records.append((page_index, crop_record.block_index, crop_record.crop))

                if crop_records:
                    texts, _ = engine.process_crops(
                        [crop for _, _, crop in crop_records],
                        batch_size=effective_batch_size,
                    )
                    for (page_index, block_index, _), text in zip(crop_records, texts):
                        page_blk_list = pages[page_index][1]
                        page_blk_list[block_index].text = text

                for page_index, _image, blk_list in group_items:
                    results[page_index] = self.sanitize_block_texts(blk_list)
            else:
                for page_index, image, blk_list in group_items:
                    results[page_index] = self.sanitize_block_texts(
                        engine.process_image(image, blk_list)
                    )

        return [result if result is not None else [] for result in results]
            
    def _set_source_language(self, blk_list: list[TextBlock]) -> None:
        source_lang_code = language_codes.get(self.source_lang_english, 'en')
        for blk in blk_list:
            blk.source_lang = source_lang_code

    def _get_ocr_key(self, localized_ocr: str) -> str:
        translator_map = {
            self.settings.ui.tr('GPT-4.1-mini'): 'GPT-4.1-mini',
            self.settings.ui.tr('Microsoft OCR'): 'Microsoft OCR',
            self.settings.ui.tr('Google Cloud Vision'): 'Google Cloud Vision',
            self.settings.ui.tr('Gemini-2.0-Flash'): 'Gemini-2.0-Flash',
            self.settings.ui.tr('Tencent/HunyuanOCR'): 'Tencent/HunyuanOCR',
            self.settings.ui.tr('Default'): 'Default',
        }
        return translator_map.get(localized_ocr, localized_ocr)
