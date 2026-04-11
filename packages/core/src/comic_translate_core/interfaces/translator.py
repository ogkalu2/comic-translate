"""
Translator interface for text translation services.
"""

from abc import ABC, abstractmethod
from typing import Dict, List, Optional


class ITranslator(ABC):
    """
    Interface for text translation services.
    
    Translates text between languages with support for context and glossary.
    """

    @abstractmethod
    def translate(
        self,
        text: str,
        source_lang: str,
        target_lang: str,
        context: Optional[str] = None,
    ) -> str:
        """
        Translate text from source language to target language.

        Args:
            text: Text to translate
            source_lang: Source language code (ISO 639-1)
            target_lang: Target language code (ISO 639-1)
            context: Optional context for better translation

        Returns:
            Translated text
        """
        ...

    @abstractmethod
    def translate_batch(
        self,
        texts: List[str],
        source_lang: str,
        target_lang: str,
        context: Optional[str] = None,
    ) -> List[str]:
        """
        Translate multiple texts in batch.

        Args:
            texts: List of texts to translate
            source_lang: Source language code (ISO 639-1)
            target_lang: Target language code (ISO 639-1)
            context: Optional context for better translation

        Returns:
            List of translated texts
        """
        ...

    @abstractmethod
    def translate_with_glossary(
        self,
        text: str,
        source_lang: str,
        target_lang: str,
        glossary: Dict[str, str],
    ) -> str:
        """
        Translate text with glossary enforcement.

        Args:
            text: Text to translate
            source_lang: Source language code (ISO 639-1)
            target_lang: Target language code (ISO 639-1)
            glossary: Dictionary mapping source terms to target translations

        Returns:
            Translated text with glossary terms applied
        """
        ...

    @abstractmethod
    def get_supported_pairs(self) -> List[tuple]:
        """
        Get list of supported language pairs.

        Returns:
            List of (source_lang, target_lang) tuples
        """
        ...

    @abstractmethod
    def get_translator_name(self) -> str:
        """
        Get the name/identifier of this translator.

        Returns:
            Translator name (e.g., "deepl", "gpt", "claude")
        """
        ...
