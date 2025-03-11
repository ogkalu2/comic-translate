from typing import Any
import numpy as np

from .base import BaseLLMTranslation
from ...utils.translator_utils import get_llm_client, encode_image_array, MODEL_MAP


class ClaudeTranslation(BaseLLMTranslation):
    """Translation engine using Anthropic Claude models."""
    
    def __init__(self):
        """Initialize Claude translation engine."""
        super().__init__()
        self.model_name = None
    
    def initialize(self, settings: Any, source_lang: str, target_lang: str, model_name: str, **kwargs) -> None:
        """
        Initialize Claude translation engine.
        
        Args:
            settings: Settings object with credentials
            source_lang: Source language name
            target_lang: Target language name
            model_name: Claude model name
        """
        super().initialize(settings, source_lang, target_lang, **kwargs)
        
        self.model_name = model_name
        credentials = settings.get_credentials(settings.ui.tr('Anthropic Claude'))
        self.api_key = credentials.get('api_key', '')
        self.client = get_llm_client('Claude', self.api_key)
        self.model = MODEL_MAP.get(self.model_name)
    
    def _perform_translation(self, user_prompt: str, system_prompt: str, image: np.ndarray) -> str:
        media_type = "image/png"
        
        if self.img_as_llm_input:
            encoded_image = encode_image_array(image)
            message = [
                {"role": "user", "content": [
                    {"type": "text", "text": user_prompt}, 
                    {"type": "image", "source": {"type": "base64", "media_type": media_type, "data": encoded_image}}
                ]}
            ]
        else:
            message = [
                {"role": "user", "content": [{"type": "text", "text": user_prompt}]}
            ]

        response = self.client.messages.create(
            model=self.model,
            system=system_prompt,
            messages=message,
            temperature=1,
            max_tokens=5000,
        )
        
        return response.content[0].text