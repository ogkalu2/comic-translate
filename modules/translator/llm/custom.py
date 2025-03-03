from typing import Any
import numpy as np

from .base import BaseLLMTranslation
from ...utils.translator_utils import get_llm_client, encode_image_array


class CustomTranslation(BaseLLMTranslation):
    """Translation engine using custom LLM configurations."""
    
    def __init__(self):
        """Initialize Custom LLM translation engine."""
        super().__init__()
    
    def initialize(self, settings: Any, source_lang: str, target_lang: str, **kwargs) -> None:
        """
        Initialize Custom LLM translation engine.
        
        Args:
            settings: Settings object with credentials
            source_lang: Source language name
            target_lang: Target language name
            **kwargs: Additional parameters
        """
        super().initialize(settings, source_lang, target_lang, **kwargs)
        
        credentials = settings.get_credentials(settings.ui.tr('Custom'))
        self.api_key = credentials.get('api_key', "")
        self.api_url = credentials.get('api_url', "")
        self.model = credentials.get('model', "")
        self.client = get_llm_client('GPT', self.api_key, self.api_url)
    
    def _perform_translation(self, user_prompt: str, system_prompt: str, image: np.ndarray) -> str:
        """
        Perform translation using Custom model (default to GPT-like interface).
        
        Args:
            user_prompt: User prompt for LLM
            system_prompt: System prompt for LLM
            image: Image as numpy array
            
        Returns:
            Translated JSON text
        """
        encoded_image = None
        if self.img_as_llm_input:
            encoded_image = encode_image_array(image)
            
            message = [
                {"role": "system", "content": [{"type": "text", "text": system_prompt}]},
                {"role": "user", "content": [
                    {"type": "text", "text": user_prompt}, 
                    {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{encoded_image}"}}
                ]}
            ]
        else:
            message = [
                {"role": "system", "content": [{"type": "text", "text": system_prompt}]},
                {"role": "user", "content": [{"type": "text", "text": user_prompt}]}
            ]

        response = self.client.chat.completions.create(
            model=self.model,
            messages=message,
            temperature=1,
            max_tokens=5000,
        )

        return response.choices[0].message.content