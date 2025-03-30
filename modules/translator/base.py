from abc import ABC, abstractmethod
from typing import Any
import numpy as np

from ..utils.textblock import TextBlock


class TranslationEngine(ABC):
    """
    Abstract base class for all translation engines.
    Defines common interface and utility methods.
    """
    
    @abstractmethod
    def initialize(self, settings: Any, source_lang: str, target_lang: str, **kwargs) -> None:
        """
        Initialize the translation engine with necessary parameters.
        
        Args:
            settings: Settings object with credentials
            source_lang: Source language name
            target_lang: Target language name
            **kwargs: Engine-specific initialization parameters
        """
        pass
    
    @abstractmethod
    def translate(self, *args, **kwargs) -> Any:
        """
        Abstract method for translating text.
        Must be implemented by all subclasses with appropriate signatures.
        
        Returns:
            Translated text or updated TextBlock objects
        """
        pass
    
    def get_language_code(self, language: str) -> str:
        """
        Get standardized language code from language name.
        
        Args:
            language: Language name
            
        Returns:
            Standardized language code
        """
        from ..utils.pipeline_utils import get_language_code
        return get_language_code(language)


class TraditionalTranslation(TranslationEngine):
    """Base class for traditional translation engines (non-LLM)."""
    
    @abstractmethod
    def translate(self, blk_list: list[TextBlock]) -> list[TextBlock]:
        """
        Translate text blocks using text-based API.
        
        Args:
            blk_list: List of TextBlock objects containing text to translate
            
        Returns:
            List of updated TextBlock objects with translations
        """
        pass


class LLMTranslation(TranslationEngine):
    """Base class for LLM-based translation engines."""
    
    @abstractmethod
    def translate(self, blk_list: list[TextBlock], image: np.ndarray, extra_context: str) -> list[TextBlock]:
        """
        Translate text blocks using LLM.
        
        Args:
            blk_list: List of TextBlock objects containing text to translate
            image: Image as numpy array (for context)
            extra_context: Additional context information for translation
            
        Returns:
            List of updated TextBlock objects with translations
        """
        pass
    
    def get_system_prompt(self, source_lang: str, target_lang: str) -> str:
        """
        Get system prompt for LLM translation.
        
        Args:
            source_lang: Source language
            target_lang: Target language
            
        Returns:
            Formatted system prompt
        """
        return f"""You are an expert translator who translates {source_lang} to {target_lang}. You pay attention to style, formality, idioms, slang etc and try to convey it in the way a {target_lang} speaker would understand.
        BE MORE NATURAL. NEVER USE 당신, 그녀, 그 or its Japanese equivalents.
        Specifically, you will be translating text OCR'd from a comic. The OCR is not perfect and as such you may receive text with typos or other mistakes.
        To aid you and provide context, You may be given the image of the page and/or extra context about the comic. You will be given a json string of the detected text blocks and the text to translate. Return the json string with the texts translated. DO NOT translate the keys of the json. For each block:
        - If it's already in {target_lang} or looks like gibberish, OUTPUT IT AS IT IS instead
        - DO NOT give explanations
        Do Your Best! I'm really counting on you."""