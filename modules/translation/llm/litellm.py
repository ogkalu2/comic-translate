from typing import Any
import numpy as np
import litellm

from .base import BaseLLMTranslation


class LiteLLMTranslation(BaseLLMTranslation):
    """Translation engine using LiteLLM as a unified AI gateway.

    Supports 100+ LLM providers (OpenAI, Anthropic, Google, Azure,
    AWS Bedrock, Ollama, and more) through a single interface.
    Users specify a LiteLLM model string such as
    ``anthropic/claude-sonnet-4-6`` or ``openai/gpt-4.1``.
    """

    def __init__(self):
        super().__init__()
        self.supports_images = True

    def initialize(self, settings: Any, source_lang: str, target_lang: str,
                   tr_key: str = "LiteLLM", **kwargs) -> None:
        super().initialize(settings, source_lang, target_lang, **kwargs)

        credentials = settings.get_credentials(settings.ui.tr(tr_key))
        self.api_key = credentials.get('api_key', '')
        self.model = credentials.get('model', '')
        self.timeout = 120

    def _perform_translation(self, user_prompt: str, system_prompt: str,
                             image: np.ndarray) -> str:
        if self.supports_images and self.img_as_llm_input and image is not None:
            encoded_image, mime_type = self.encode_image(image)
            messages = [
                {
                    "role": "system",
                    "content": [{"type": "text", "text": system_prompt}]
                },
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": user_prompt},
                        {"type": "image_url", "image_url": {
                            "url": f"data:{mime_type};base64,{encoded_image}"
                        }}
                    ]
                }
            ]
        else:
            messages = [
                {
                    "role": "system",
                    "content": [{"type": "text", "text": system_prompt}]
                },
                {
                    "role": "user",
                    "content": [{"type": "text", "text": user_prompt}]
                }
            ]

        kwargs = {
            "model": self.model,
            "messages": messages,
            "temperature": self.temperature,
            "max_tokens": self.max_tokens,
            "drop_params": True,
            "timeout": self.timeout,
        }

        if self.api_key:
            kwargs["api_key"] = self.api_key

        try:
            response = litellm.completion(**kwargs)
            return response.choices[0].message.content
        except Exception as e:
            raise RuntimeError(f"LiteLLM API request failed: {e}")
