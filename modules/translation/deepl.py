from typing import Any

from .base import TraditionalTranslation
from ..utils.textblock import TextBlock


class DeepLTranslation(TraditionalTranslation):
    """Translation engine using DeepL API."""

    def __init__(self):
        self.source_lang_code = None
        self.target_lang_code = None
        self.api_key = None
        self.translator = None
        self.target_lang = None # This is unused, can be removed if not needed elsewhere

    def initialize(self, settings: Any, source_lang: str, target_lang: str) -> None:

        import deepl

        # get the “raw” code (e.g. “en”, “zh”, etc.)
        raw_src = self.get_language_code(source_lang)
        raw_tgt = self.get_language_code(target_lang)

        # Use different processing for source and target languages
        self.source_lang_code = self.preprocess_source_language(raw_src)
        self.target_lang_code = self.preprocess_target_language(raw_tgt)

        credentials = settings.get_credentials(settings.ui.tr("DeepL"))
        self.api_key = credentials.get('api_key', '')

        # It's good practice to check for the API key before creating the translator
        if not self.api_key:
            raise ValueError("DeepL API key not found in settings.")

        self.translator = deepl.Translator(self.api_key)

    def translate(self, blk_list: list[TextBlock]) -> list[TextBlock]:
        try:
            # Prepare a list of texts to translate for better efficiency (if texts are not empty)
            texts_to_translate = []
            for blk in blk_list:
                text = self.preprocess_text(blk.text, self.source_lang_code)
                # Keep track of empty texts to avoid sending them to the API
                if not text.strip():
                    blk.translation = ''
                else:
                    texts_to_translate.append(text)

            # Only call the API if there is something to translate
            if not texts_to_translate:
                return blk_list

            # The deepl library can translate a list of strings in one call, which is more efficient
            results = self.translator.translate_text(
                texts_to_translate,
                source_lang=self.source_lang_code,
                target_lang=self.target_lang_code
            )

            # Map the results back to the original blocks
            result_iterator = iter(results)
            for blk in blk_list:
                # If the original text was not empty, get the next translation result
                if blk.text.strip():
                    blk.translation = next(result_iterator).text

        except deepl.DeepLException as e:
            # It's better to catch the specific DeepL exception
            print(f"DeepL Translator error: {str(e)}")
        except Exception as e:
            # Catch other potential errors
            print(f"An unexpected error occurred: {str(e)}")

        return blk_list

    def preprocess_source_language(self, lang_code: str) -> str:
        """Prepares a language code for the 'source_lang' parameter."""
        # For source language, DeepL expects the base code (e.g., 'EN', 'ZH').
        # We take the first part of the code (e.g., 'zh' from 'zh-CN') and uppercase it.
        base_lang = lang_code.split('-')[0]
        return base_lang.upper()

    def preprocess_target_language(self, lang_code: str) -> str:
        """Prepares a language code for the 'target_lang' parameter."""
        code = lang_code.lower()
        if code == 'zh-cn':
            return 'ZH-HANS'  # DeepL: Simplified Chinese
        if code == 'zh-tw':
            return 'ZH-HANT'  # DeepL: Traditional Chinese
        if code == 'en':
            return 'EN-US'
        if code == 'pt':
            return 'PT-BR'
        return lang_code.upper()
