"""
Ollama Translation Engine
Provides local, free translation using Ollama-hosted models (e.g., gemma2, llama3.1)
"""
from typing import Any
import requests
import json

from .base import BaseLLMTranslation


class OllamaTranslation(BaseLLMTranslation):
    """Translation engine using local Ollama models with OpenAI-compatible API."""
    
    def __init__(self):
        super().__init__()
        self.model_name = None
        self.api_base_url = "http://localhost:11434/v1"  # Default Ollama endpoint
        self.supports_images = False  # Most Ollama models don't support images yet
        self.timeout = 180  # Longer timeout for local models
    
    def initialize(self, settings: Any, source_lang: str, target_lang: str, **kwargs) -> None:
        """
        Initialize Ollama translation engine.
        
        Args:
            settings: Settings object with credentials
            source_lang: Source language name
            target_lang: Target language name
        """
        super().initialize(settings, source_lang, target_lang, **kwargs)
        
        # Get Ollama-specific configuration
        credentials = settings.get_credentials(settings.ui.tr('Ollama'))
        # Read model name and ensure a sensible default when empty or missing
        model_cfg = credentials.get('model', '') if credentials else ''
        if isinstance(model_cfg, str):
            model_cfg = model_cfg.strip()
        if not model_cfg:
            model_cfg = 'gemma2:9b'
        self.model_name = model_cfg
        
        # Allow custom Ollama URL (for remote Ollama instances)
        custom_url = credentials.get('api_url', '').strip()
        if custom_url:
            self.api_base_url = custom_url.rstrip('/')
        
        # Ollama doesn't require API key, but we keep it for compatibility
        self.api_key = credentials.get('api_key', 'ollama')
        
        # Detect if model supports vision (future-proofing)
        vision_models = ['llava', 'bakllava', 'moondream']
        self.supports_images = any(vm in self.model_name.lower() for vm in vision_models)
    
    def _perform_translation(self, user_prompt: str, system_prompt: str, image=None) -> str:
        """
        Perform translation using Ollama's native API.
        
        Args:
            user_prompt: Text prompt from user
            system_prompt: System instructions
            image: Optional image (not used for most Ollama models)
            
        Returns:
            Translated text
        """
        # Combine system prompt + user prompt into single prompt
        # Ollama's native /api/generate endpoint works better than OpenAI-compatible
        full_prompt = f"{system_prompt}\n\n{user_prompt}"
        
        payload = {
            "model": self.model_name,
            "prompt": full_prompt,
            "temperature": 0.3,  # Lower temperature for more consistent translations
            "stream": False
        }
        
        headers = {
            "Content-Type": "application/json",
        }
        
        try:
            # Use Ollama's native /api/generate endpoint instead of OpenAI-compatible
            api_url = self.api_base_url.replace('/v1', '')  # Remove /v1 if present
            response = requests.post(
                f"{api_url}/api/generate",
                headers=headers,
                json=payload,
                timeout=self.timeout
            )
            response.raise_for_status()
            result = response.json()
            
            # Extract response from native Ollama format
            if 'response' in result:
                translated_text = result['response'].strip()
                return translated_text
            else:
                raise ValueError(f"Unexpected response format from Ollama: {result}")
                
        except requests.exceptions.ConnectionError:
            raise ConnectionError(
                "Could not connect to Ollama. Please ensure:\n"
                "1. Ollama is installed (download from https://ollama.com)\n"
                "2. Ollama service is running (check system tray or run 'ollama serve')\n"
                f"3. The model '{self.model_name}' is installed (run 'ollama pull {self.model_name}')"
            )
        except requests.exceptions.Timeout:
            raise TimeoutError(
                f"Ollama request timed out after {self.timeout}s. "
                "Local models can be slow. Try a smaller model or increase timeout."
            )
        except requests.exceptions.HTTPError as e:
            if e.response.status_code == 404:
                raise ValueError(
                    f"Model '{self.model_name}' not found. "
                    f"Install it with: ollama pull {self.model_name}"
                )
            raise
    
    def get_available_models(self) -> list:
        """
        Query Ollama for available models on the system.
        
        Returns:
            List of model names
        """
        try:
            # Ollama has a tags endpoint but it's not OpenAI-compatible
            # We'll use the native Ollama API for this
            base_url = self.api_base_url.replace('/v1', '')
            response = requests.get(f"{base_url}/api/tags", timeout=5)
            response.raise_for_status()
            result = response.json()
            
            if 'models' in result:
                return [model['name'] for model in result['models']]
            return []
        except:
            # If we can't query, return common recommendations
            return [
                'gemma2:9b',
                'llama3.1:8b', 
                'qwen2.5:7b',
                'mistral:7b'
            ]
