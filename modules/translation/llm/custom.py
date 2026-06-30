from typing import Any
from .gpt import GPTTranslation


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
        
        # Get custom credentials instead of OpenAI credentials
        credentials = settings.get_credentials(settings.ui.tr(tr_key))
        self.api_key = credentials.get('api_key', '')
        self.model = credentials.get('model', '')
        
        # Override the API base URL with the custom one
        # Strip trailing slashes and remove any /chat/completions endpoint path
        api_url = credentials.get('api_url', '').rstrip('/')
        # Remove /chat/completions if it's already in the URL (to prevent duplication)
        if api_url.endswith('/chat/completions'):
            api_url = api_url.rsplit('/chat/completions', 1)[0]
        self.api_base_url = api_url
        self.timeout = 120  # Custom timeout for potentially slower custom LLMs