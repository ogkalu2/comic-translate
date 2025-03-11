from typing import Any
import numpy as np
import requests

from .base import BaseLLMTranslation
from ...utils.translator_utils import MODEL_MAP


class GeminiTranslation(BaseLLMTranslation):
    """Translation engine using Google Gemini models via REST API."""
    
    def __init__(self):
        super().__init__()
        self.model_name = None
        self.api_key = None
        self.api_base_url = "https://generativelanguage.googleapis.com/v1beta/models"
    
    def initialize(self, settings: Any, source_lang: str, target_lang: str, model_name: str, **kwargs) -> None:
        """
        Initialize Gemini translation engine.
        
        Args:
            settings: Settings object with credentials
            source_lang: Source language name
            target_lang: Target language name
            model_name: Gemini model name
        """
        super().initialize(settings, source_lang, target_lang, **kwargs)
        
        self.model_name = model_name
        credentials = settings.get_credentials(settings.ui.tr('Google Gemini'))
        self.api_key = credentials.get('api_key', '')
        
        # Map friendly model name to API model name
        self.model = MODEL_MAP.get(self.model_name)
    
    def _perform_translation(self, user_prompt: str, system_prompt: str, image: np.ndarray) -> str:
        """
        Perform translation using Gemini REST API.
        
        Args:
            user_prompt: The prompt to send to the model
            system_prompt: System instructions for the model
            image: Image data as numpy array
            
        Returns:
            Translated text from the model
        """
        # Create API endpoint URL
        url = f"{self.api_base_url}/{self.model}:generateContent?key={self.api_key}"
        
        # Setup generation config
        generation_config = {
            "temperature": 1,
            "topP": 0.95,
            "topK": 0,
            "maxOutputTokens": 5000,
        }
        
        # Setup safety settings
        safety_settings = [
            {"category": "HARM_CATEGORY_HARASSMENT", "threshold": "BLOCK_NONE"},
            {"category": "HARM_CATEGORY_HATE_SPEECH", "threshold": "BLOCK_NONE"},
            {"category": "HARM_CATEGORY_SEXUALLY_EXPLICIT", "threshold": "BLOCK_NONE"},
            {"category": "HARM_CATEGORY_DANGEROUS_CONTENT", "threshold": "BLOCK_NONE"},
        ]
        
        # Prepare parts for the request
        parts = []
        
        # Add image if needed
        if self.img_as_llm_input:
            # Base64 encode the image

            img_b64, mime_type = self.encode_image(image)
            parts.append({
                "inline_data": {
                    "mime_type": mime_type,
                    "data": img_b64
                }
            })
        
        # Add text prompt
        parts.append({"text": user_prompt})
        
        # Create the request payload
        payload = {
            "contents": [{
                "parts": parts
            }],
            "generationConfig": generation_config,
            "safetySettings": safety_settings
        }
        
        # Add system instructions if provided
        if system_prompt:
            payload["systemInstruction"] = {"parts": [{"text": system_prompt}]}
        
        # Send request to Gemini API
        headers = {
            "Content-Type": "application/json"
        }
        
        response = requests.post(url, headers=headers, json=payload)
        
        # Handle response
        if response.status_code != 200:
            error_msg = f"API request failed with status code {response.status_code}: {response.text}"
            raise Exception(error_msg)
        
        # Extract text from response
        response_data = response.json()
        
        try:
            # Extract the generated text from the response
            candidates = response_data.get("candidates", [])
            if not candidates:
                return "No response generated"
            
            content = candidates[0].get("content", {})
            parts = content.get("parts", [])
            
            # Concatenate all text parts
            result = ""
            for part in parts:
                if "text" in part:
                    result += part["text"]
            
            return result
        except (KeyError, IndexError) as e:
            raise Exception(f"Failed to parse API response: {str(e)}")