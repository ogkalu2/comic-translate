"""
Translation adapter for wrapping translation package implementations.
"""

from typing import Any, Dict, List, Optional
import numpy as np

from ..interfaces.translator import ITranslator


class TranslationAdapter:
    """
    Adapter for translation engines.
    Wraps the translation package to implement core interfaces.
    """

    def __init__(self, engine_type: str = "gpt", **kwargs):
        self.engine_type = engine_type
        self._engine = None
        self._kwargs = kwargs

    def _get_engine(self):
        """Lazy load the translation engine."""
        if self._engine is None:
            from comic_translate_translation.engine import TranslationEngineFactory
            self._engine = TranslationEngineFactory.create_engine(
                engine_type=self.engine_type,
                **self._kwargs
            )
        return self._engine

    def translate(self, blk_list: list, **kwargs) -> list:
        """
        Translate text blocks.

        Args:
            blk_list: List of text blocks to translate
            **kwargs: Additional translation parameters

        Returns:
            List of translated text blocks
        """
        engine = self._get_engine()
        return engine.translate(blk_list, **kwargs)


class TranslatorAdapter(ITranslator):
    """Adapter implementing ITranslator interface."""

    def __init__(self, engine_type: str = "gpt", **kwargs):
        self._adapter = TranslationAdapter(engine_type=engine_type, **kwargs)

    def translate(
        self,
        text: str,
        source_lang: str,
        target_lang: str,
        context: Optional[str] = None,
    ) -> str:
        """Translate text from source to target language."""
        from modules.utils.textblock import TextBlock
        blk = TextBlock()
        blk.text = text

        result = self._adapter.translate(
            [blk],
            source_lang=source_lang,
            target_lang=target_lang,
            context=context
        )
        if result:
            return result[0].translation or text
        return text

    def translate_batch(
        self,
        texts: List[str],
        source_lang: str,
        target_lang: str,
        context: Optional[str] = None,
    ) -> List[str]:
        """Translate multiple texts in batch."""
        from modules.utils.textblock import TextBlock
        blocks = []
        for text in texts:
            blk = TextBlock()
            blk.text = text
            blocks.append(blk)

        result = self._adapter.translate(
            blocks,
            source_lang=source_lang,
            target_lang=target_lang,
            context=context
        )
        return [blk.translation or blk.text for blk in result]
