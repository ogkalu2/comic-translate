from typing import Any

from .gpt import GPTTranslation
from ...utils.translator_utils import MODEL_MAP


class MinimaxTranslation(GPTTranslation):
    """Translation engine using MiniMax models with OpenAI-compatible API."""

    def __init__(self):
        super().__init__()
        self.supports_images = True
        self.api_base_url = "https://api.minimax.io/v1"

    def initialize(self, settings: Any, source_lang: str, target_lang: str, model_name: str, **kwargs) -> None:
        """
        Initialize MiniMax translation engine.

        Args:
            settings: Settings object with credentials
            source_lang: Source language name
            target_lang: Target language name
            model_name: MiniMax model name
        """
        # Call BaseLLMTranslation's initialize to skip GPT-specific credential loading
        super(GPTTranslation, self).initialize(settings, source_lang, target_lang, **kwargs)

        self.model_name = model_name
        credentials = settings.get_credentials(settings.ui.tr('MiniMax'))
        self.api_key = credentials.get('api_key', '')
        self.model = MODEL_MAP.get(self.model_name)
