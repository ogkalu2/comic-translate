from typing import Any

from .gpt import GPTTranslation
from ...utils.translator_utils import MODEL_MAP


class GrokTranslation(GPTTranslation):
    """Translation engine for xAI Grok models using OpenAI-compatible API."""

    def __init__(self):
        super().__init__()
        self.api_base_url = "https://api.x.ai/v1"
        self.supports_images = True

    def initialize(self, settings: Any, source_lang: str, target_lang: str, model_name: str, **kwargs) -> None:
        """Initialize Grok translation engine.

        Args:
            settings: Settings object with credentials
            source_lang: Source language name
            target_lang: Target language name
            model_name: Grok model name (e.g., 'grok-4-0709')
        """
        # Call BaseLLMTranslation's initialize (skip GPTTranslation override because of different credential label)
        super(GPTTranslation, self).initialize(settings, source_lang, target_lang, **kwargs)

        self.model_name = model_name
        credentials = settings.get_credentials(settings.ui.tr('xAI'))
        self.api_key = credentials.get('api_key', '')
        self.model = MODEL_MAP.get(self.model_name)
