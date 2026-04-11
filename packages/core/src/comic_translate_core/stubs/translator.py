"""
Stub translator implementation for testing.
"""

from typing import Dict, List, Optional, Tuple

from ..interfaces import ITranslator


class StubTranslator(ITranslator):
    """
    Stub translator that returns predefined translations.
    
    Useful for testing the pipeline without actual translation services.
    """

    def __init__(
        self,
        translation_map: Optional[Dict[str, str]] = None,
        default_translation: str = "Translated text",
    ):
        """
        Initialize with optional translation mapping.

        Args:
            translation_map: Dictionary mapping source text to translated text
            default_translation: Default translation for unmapped text
        """
        self.translation_map = translation_map or {}
        self.default_translation = default_translation

    def translate(
        self,
        text: str,
        source_lang: str,
        target_lang: str,
        context: Optional[str] = None,
    ) -> str:
        """
        Return predefined translation for text.

        Args:
            text: Text to translate
            source_lang: Source language code (ignored)
            target_lang: Target language code (ignored)
            context: Optional context (ignored)

        Returns:
            Translated text
        """
        return self.translation_map.get(text, self.default_translation)

    def translate_batch(
        self,
        texts: List[str],
        source_lang: str,
        target_lang: str,
        context: Optional[str] = None,
    ) -> List[str]:
        """
        Return predefined translations for multiple texts.

        Args:
            texts: List of texts to translate
            source_lang: Source language code (ignored)
            target_lang: Target language code (ignored)
            context: Optional context (ignored)

        Returns:
            List of translated texts
        """
        return [self.translate(text, source_lang, target_lang, context) for text in texts]

    def translate_with_glossary(
        self,
        text: str,
        source_lang: str,
        target_lang: str,
        glossary: Dict[str, str],
    ) -> str:
        """
        Return translation with glossary terms applied.

        Args:
            text: Text to translate
            source_lang: Source language code (ignored)
            target_lang: Target language code (ignored)
            glossary: Dictionary mapping source terms to target translations

        Returns:
            Translated text with glossary terms applied
        """
        translated = self.translate(text, source_lang, target_lang)
        
        # Apply glossary terms
        for source_term, target_term in glossary.items():
            if source_term in translated:
                translated = translated.replace(source_term, target_term)
        
        return translated

    def get_supported_pairs(self) -> List[Tuple[str, str]]:
        """
        Get list of supported language pairs.

        Returns:
            List of (source_lang, target_lang) tuples
        """
        return [
            ("en", "ja"),
            ("ja", "en"),
            ("ko", "en"),
            ("en", "ko"),
            ("zh", "en"),
            ("en", "zh"),
        ]

    def get_translator_name(self) -> str:
        """
        Get the name/identifier of this translator.

        Returns:
            Translator name
        """
        return "stub"
