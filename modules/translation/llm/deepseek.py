from typing import Any
import numpy as np

from .base import BaseLLMTranslation
from ...utils.translator_utils import get_llm_client, MODEL_MAP


class DeepseekTranslation(BaseLLMTranslation):
    """Translation engine using Deepseek models."""
    
    def __init__(self):
        super().__init__()
        self.model_name = None
    
    def initialize(self, settings: Any, source_lang: str, target_lang: str, model_name: str, **kwargs) -> None:
        """
        Initialize Deepseek translation engine.
        
        Args:
            settings: Settings object with credentials
            source_lang: Source language name
            target_lang: Target language name
            model_name: Deepseek model name
        """
        super().initialize(settings, source_lang, target_lang, **kwargs)
        
        self.model_name = model_name
        credentials = settings.get_credentials(settings.ui.tr('Deepseek'))
        self.api_key = credentials.get('api_key', '')
        self.client = get_llm_client('Deepseek', self.api_key)
        self.model = MODEL_MAP.get(self.model_name)
    
    def _perform_translation(self, user_prompt: str, system_prompt: str, image: np.ndarray) -> str:
        message = [
            {"role": "system", "content": [{"type": "text", "text": system_prompt}]},
            {"role": "user", "content": [{"type": "text", "text": user_prompt}]}
        ]

        response = self.client.chat.completions.create(
            model=self.model,
            messages=message,
            temperature=0.7,
            max_tokens=1000,
        )

        return response.choices[0].message.content