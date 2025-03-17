from typing import Any
import numpy as np

from .base import BaseLLMTranslation
from ...utils.translator_utils import get_llm_client, MODEL_MAP


class DeepseekTranslation(BaseLLMTranslation):
    """Translation engine using Deepseek models."""
    
    def __init__(self):
        """Initialize Deepseek translation engine."""
        super().__init__()
        self.model_type = None
    
    def initialize(self, settings: Any, source_lang: str, target_lang: str, **kwargs) -> None:
        """
        Initialize Deepseek translation engine.
        
        Args:
            settings: Settings object with credentials
            source_lang: Source language name
            target_lang: Target language name
            **kwargs: Additional parameters including model_type
        """
        super().initialize(settings, source_lang, target_lang, **kwargs)
        
        self.model_type = kwargs.get('model_type', 'Deepseek-v3')
        credentials = settings.get_credentials(settings.ui.tr('Deepseek'))
        self.api_key = credentials['api_key']
        self.client = get_llm_client('Deepseek', self.api_key)
        # Deepseek model is fixed as "deepseek-chat"
    
    def _perform_translation(self, user_prompt: str, system_prompt: str, image: np.ndarray) -> str:
        """
        Perform translation using Deepseek model.
        
        Args:
            user_prompt: User prompt for Deepseek
            system_prompt: System prompt for Deepseek
            image: Image as numpy array (ignored as Deepseek doesn't support images)
            
        Returns:
            Translated JSON text
        """
        message = [
            {"role": "system", "content": [{"type": "text", "text": system_prompt}]},
            {"role": "user", "content": [{"type": "text", "text": user_prompt}]}
        ]
        print(message)

        response = self.client.chat.completions.create(
            model="deepseek-chat",
            messages=message,
            temperature=0.7,
            max_tokens=1000,
        )
        print(response.choices[0].message.content)

        return response.choices[0].message.content