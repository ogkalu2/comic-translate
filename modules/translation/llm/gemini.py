from typing import Any
import numpy as np

from .base import BaseLLMTranslation
from ...utils.translator_utils import get_llm_client, MODEL_MAP
from ...rendering.render import cv2_to_pil


class GeminiTranslation(BaseLLMTranslation):
    """Translation engine using Google Gemini models."""
    
    def __init__(self):
        """Initialize Gemini translation engine."""
        super().__init__()
        self.model_type = None
    
    def initialize(self, settings: Any, source_lang: str, target_lang: str, **kwargs) -> None:
        """
        Initialize Gemini translation engine.
        
        Args:
            settings: Settings object with credentials
            source_lang: Source language name
            target_lang: Target language name
            **kwargs: Additional parameters including model_type
        """
        super().initialize(settings, source_lang, target_lang, **kwargs)
        
        self.model_type = kwargs.get('model_type', 'Gemini-2.0-Pro')
        credentials = settings.get_credentials(settings.ui.tr('Google Gemini'))
        self.api_key = credentials['api_key']
        self.client = get_llm_client('Gemini', self.api_key)
        self.model = MODEL_MAP.get(self.model_type, 'gemini-2.0-pro')
    
    def _perform_translation(self, user_prompt: str, system_prompt: str, image: np.ndarray) -> str:
        """
        Perform translation using Gemini model.
        
        Args:
            user_prompt: User prompt for Gemini
            system_prompt: System prompt for Gemini
            image: Image as numpy array
            
        Returns:
            Translated JSON text
        """
        generation_config = {
            "temperature": 1,
            "top_p": 0.95,
            "top_k": 0,
            "max_output_tokens": 5000,
        }
        
        safety_settings = [
            {"category": "HARM_CATEGORY_HARASSMENT", "threshold": "BLOCK_NONE"},
            {"category": "HARM_CATEGORY_HATE_SPEECH", "threshold": "BLOCK_NONE"},
            {"category": "HARM_CATEGORY_SEXUALLY_EXPLICIT", "threshold": "BLOCK_NONE"},
            {"category": "HARM_CATEGORY_DANGEROUS_CONTENT", "threshold": "BLOCK_NONE"},
        ]

        # Convert image to PIL format for Gemini
        pil_image = cv2_to_pil(image)
        
        model_instance = self.client.GenerativeModel(
            model_name=self.model,
            generation_config=generation_config, 
            system_instruction=system_prompt, 
            safety_settings=safety_settings
        )
        
        chat = model_instance.start_chat(history=[])
        
        if self.img_as_llm_input:
            chat.send_message([pil_image, user_prompt])
        else:
            chat.send_message([user_prompt])
            
        return chat.last.text