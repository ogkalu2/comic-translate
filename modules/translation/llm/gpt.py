from typing import Any, Optional, Union, List
import json
import numpy as np
import requests
import logging
from .base import BaseLLMTranslation
from ...utils.translator_utils import MODEL_MAP


class GPTTranslation(BaseLLMTranslation):
    """
    Translation engine using local vLLM (OpenAI-compatible) through direct REST API calls.
    Designed for minimal prompt overhead and strict JSON outputs.
    """

    def __init__(self) -> None:
        super().__init__()
        self.model_name: Optional[str] = None
        self.model: Optional[str] = None
        self.last_usage = None
        # vLLM OpenAI-compatible base URL
        self.api_base_url: str = "http://localhost:8000/v1"

        # vLLM text-only in your setup; keep this False to avoid multimodal payload bloat.
        self.supports_images: bool = False

    def initialize(
        self,
        settings: Any,
        source_lang: str,
        target_lang: str,
        model_name: str,
        api_base_url: Optional[str] = None,
        **kwargs,
    ) -> None:
        super().initialize(settings, source_lang, target_lang, **kwargs)
        self.model_name = model_name
        self.model = MODEL_MAP.get(self.model_name, self.model_name)

        # Allow override from UI/config
        if api_base_url:
            self.api_base_url = api_base_url.rstrip("/")

    def _perform_translation(
        self,
        user_prompt: str,
        system_prompt: str,
        image: np.ndarray,
    ) -> str:
        """
        Sends translation request to local vLLM.
        Returns the assistant message content (JSON string).
        """

        # Minimal messages: plain strings (no multimodal wrappers).
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ]

        payload = {
            "model": self.model,
            "messages": messages,
            "temperature": 0,
            "top_p": 1,
            "max_tokens": int(self.max_tokens),
            "presence_penalty" : 0,
            "repetition_penalty" : 1.0,
            "response_format": {"type": "json_object"},
        }

        return self._make_api_request(payload)

    def _make_api_request(self, payload):
        try:
            response = requests.post(
                f"{self.api_base_url}/chat/completions",
                headers={"Content-Type": "application/json"},
                data=json.dumps(payload, ensure_ascii=False),
                timeout=self.timeout
            )

            response.raise_for_status()
            response_data = response.json()

            # --- TOKEN USAGE CAPTURE ---
            usage = response_data.get("usage")
            if usage:
                self.last_usage = usage
                logger = logging.getLogger(__name__)
                logger.info(
                    "TOKENS | prompt=%s completion=%s total=%s",
                    usage.get("prompt_tokens"),
                    usage.get("completion_tokens"),
                    usage.get("total_tokens"),
                )

            content = response_data["choices"][0]["message"]["content"]

            logger = logging.getLogger(__name__)
            logger.info("LLM RESPONSE | %s", content)

            return content

        except requests.exceptions.RequestException as e:
            error_msg = f"API request failed: {str(e)}"
            if hasattr(e, 'response') and e.response is not None:
                try:
                    error_details = e.response.json()
                    error_msg += f" - {json.dumps(error_details)}"
                except:
                    error_msg += f" - Status code: {e.response.status_code}"
            raise RuntimeError(error_msg)

    @staticmethod
    def build_minimal_json_translate_prompts(lines: List[str], target_lang: str) -> (str, str):
        system_prompt = (
            f"Translate EN to {target_lang}. "
            f"Return ONLY a JSON object: {{\"r\": [<strings>]}}. "
            f"Keep array length and order. No extra keys. No explanations."
        )
        user_prompt = json.dumps(lines, ensure_ascii=False, separators=(",", ":"))
        return user_prompt, system_prompt

    @staticmethod
    def parse_result_array(content: str) -> List[str]:
        obj = json.loads(content)
        res = obj["r"]
        if not isinstance(res, list) or not all(isinstance(x, str) for x in res):
            raise ValueError("Invalid result format: expected {'r': [str, ...]}")
        return res