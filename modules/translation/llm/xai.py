from typing import Any

from .gpt import GPTTranslation
from ...utils.translator_utils import MODEL_MAP



class xAITranslation(GPTTranslation):
    """Translation engine using xAI models with OpenAI-compatible API."""
    
    def __init__(self):
        super().__init__()
        self.supports_images = False
        self.api_base_url = "https://api.xai.ai/v1"
    
    def initialize(self, settings: Any, source_lang: str, 
                   target_lang: str, model_name: str, **kwargs) -> None:
        """
        Initialize xAI translation engine.
        
        Args:
            settings: Settings object with credentials
            source_lang: Source language name
            target_lang: Target language name
            model_name: xAI model name
        """
        # Call BaseLLMTranslation's initialize
        super(GPTTranslation
              , self).initialize(
                  settings, source_lang, target_lang, **kwargs)
        
        self.model_name = model_name
        credentials = settings.get_credentials(settings.ui.tr('xAI'))
        self.api_key = credentials.get('api_key', '')
        self.model = MODEL_MAP.get(self.model_name)


# from xai_sdk import Client
# from xai_sdk.chat import user

# client = Client()

# chat = client.chat.create("grok-4")
# chat.append(user("Whats 2 + 3?"))

# client.batch.add("batch_0da3f791-94cb-40ca-812c-40b76abe39f6", [chat])