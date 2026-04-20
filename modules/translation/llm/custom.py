from typing import Any
from .gpt import GPTTranslation

LOCAL_VLLM_DEFAULT_API_BASE_URL = "http://127.0.0.1:8000/v1"
LOCAL_VLLM_DEFAULT_MODEL = "AxionML/Qwen3.5-35B-A3B-NVFP4"
LM_STUDIO_DEFAULT_API_BASE_URL = "http://127.0.0.1:1234/v1"
LM_STUDIO_DEFAULT_MODEL = "qwen/qwen3.6-35b-a3b"


class CustomTranslation(GPTTranslation):
    """Translation engine using custom LLM configurations with OpenAI-compatible API."""
    
    def __init__(self):
        super().__init__()
    
    def initialize(self, settings: Any, source_lang: str, target_lang: str, tr_key: str, **kwargs) -> None:
        """
        Initialize custom translation engine.
        
        Args:
            settings: Settings object with credentials
            source_lang: Source language name
            target_lang: Target language name
        """
        # Call BaseLLMTranslation's initialize, not GPTTranslation's
        # to avoid the GPT-specific credential loading
        super(GPTTranslation, self).initialize(settings, source_lang, target_lang, **kwargs)
        normalized_key = tr_key or "Custom"

        if normalized_key == "LM Studio":
            self.api_key = ""
            self.model = LM_STUDIO_DEFAULT_MODEL
            self.api_base_url = LM_STUDIO_DEFAULT_API_BASE_URL
        elif normalized_key == "Local vLLM":
            self.api_key = ""
            self.model = LOCAL_VLLM_DEFAULT_MODEL
            self.api_base_url = LOCAL_VLLM_DEFAULT_API_BASE_URL
        else:
            # Get custom credentials instead of OpenAI credentials
            credentials = settings.get_credentials(settings.ui.tr(tr_key))
            self.api_key = credentials.get('api_key', '') or ''
            self.model = credentials.get('model', '') or ''
            
            # Override the API base URL with the custom one
            api_base_url = (credentials.get('api_url', '') or '').rstrip('/')
            if api_base_url and not api_base_url.endswith('/v1'):
                api_base_url = f"{api_base_url}/v1"
            self.api_base_url = api_base_url
        self.timeout = 120  # Custom timeout for potentially slower custom LLMs
