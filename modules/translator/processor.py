import numpy as np

from ..utils.textblock import TextBlock
from .base import LLMTranslation
from .factory import TranslationEngineFactory


class Translator:
    """
    Main translator class that orchestrates the translation process.
    
    Supports multiple translation engines including:
    - Text-based translators (Google, Microsoft, DeepL, Yandex)
    - LLM-based translators (GPT, Claude, Gemini, Deepseek, Custom)
    """
    
    def __init__(self, main_page, source_lang: str = "", target_lang: str = ""):
        """
        Initialize translator with settings and languages.
        
        Args:
            main_page: Main application page with settings
            source_lang: Source language name (localized)
            target_lang: Target language name (localized)
        """
        self.main_page = main_page
        self.settings = main_page.settings_page
        
        self.translator_key = self._get_translator_key(self.settings.get_tool_selection('translator'))
        
        self.source_lang = source_lang
        self.source_lang_en = self._get_english_lang(main_page, self.source_lang)
        self.target_lang = target_lang
        self.target_lang_en = self._get_english_lang(main_page, self.target_lang)
        
        # Create appropriate engine using factory
        self.engine = TranslationEngineFactory.create_engine(
            self.settings,
            self.source_lang_en,
            self.target_lang_en,
            self.translator_key
        )
        
        # Track engine type for method dispatching
        self.is_llm_engine = isinstance(self.engine, LLMTranslation)
    
    def _get_translator_key(self, localized_translator: str) -> str:
        """
        Map localized translator names to standard keys.
        
        Args:
            localized_translator: Translator name in UI language
            
        Returns:
            Standard translator key
        """
        translator_map = {
            self.settings.ui.tr("Custom"): "Custom",
            self.settings.ui.tr("Deepseek-v3"): "Deepseek-v3",
            self.settings.ui.tr("GPT-4o"): "GPT-4o",
            self.settings.ui.tr("GPT-4o mini"): "GPT-4o mini",
            self.settings.ui.tr("Claude-3-Opus"): "Claude-3-Opus",
            self.settings.ui.tr("Claude-3.7-Sonnet"): "Claude-3.7-Sonnet",
            self.settings.ui.tr("Claude-3.5-Haiku"): "Claude-3.5-Haiku",
            self.settings.ui.tr("Gemini-2.0-Flash"): "Gemini-2.0-Flash",
            self.settings.ui.tr("Gemini-2.0-Pro"): "Gemini-2.0-Pro",
            self.settings.ui.tr("Google Translate"): "Google Translate",
            self.settings.ui.tr("Microsoft Translator"): "Microsoft Translator",
            self.settings.ui.tr("DeepL"): "DeepL",
            self.settings.ui.tr("Yandex"): "Yandex",
            self.settings.ui.tr("Qwen-Max"): "Qwen-Max",
            self.settings.ui.tr("Qwen2.5 VL 72B Instruct (free)"): "Qwen2.5 VL 72B Instruct (free)",
            self.settings.ui.tr("Qwen2.5 VL 72B Instruct"): "Qwen2.5 VL 72B Instruct",
        }
        return translator_map.get(localized_translator, localized_translator)
    
    def _get_english_lang(self, main_page, translated_lang: str) -> str:
        """
        Get English language name from localized language name.
        
        Args:
            main_page: Main application page with language mapping
            translated_lang: Language name in UI language
            
        Returns:
            Language name in English
        """
        return main_page.lang_mapping.get(translated_lang, translated_lang)
    
    def translate(self, blk_list: list[TextBlock], image: np.ndarray | None = None, extra_context: str = "") -> list[TextBlock]:
        """
        Translate text in text blocks using the configured translation engine.
        
        Args:
            blk_list: List of TextBlock objects to translate
            image: Image as numpy array (for context in LLM translators)
            extra_context: Additional context information for translation
            
        Returns:
            List of updated TextBlock objects with translations
        """
        print(f"[DEBUG] Starting translation with {self.translator_key}")
        print(f"[DEBUG] Source language: {self.source_lang_en}, Target language: {self.target_lang_en}")
        print(f"[DEBUG] Number of blocks to translate: {len(blk_list)}")
        
        if self.is_llm_engine:
            print(f"[DEBUG] Using LLM translator with extra context: {bool(extra_context)}")
            # LLM translators need image and extra context
            return self.engine.translate(blk_list, image, extra_context)
        else:
            # Text-based translators only need the text blocks
            return self.engine.translate(blk_list)