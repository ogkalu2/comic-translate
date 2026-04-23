from typing import Any, Optional, Union, List
import json
import numpy as np
import requests
import logging
from .base import BaseLLMTranslation
from ...utils.local_vllm import post_json_with_wsl_fallback
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

        self.supports_images: bool = True
    
    def _is_lm_studio_backend(self) -> bool:
        base_url = (self.api_base_url or "").lower()
        return "127.0.0.1:1234" in base_url or "localhost:1234" in base_url

    def _supports_image_input(self) -> bool:
        return True

    def _build_messages(
        self,
        user_prompt: str,
        system_prompt: str,
        image: np.ndarray | None,
        *,
        include_image: bool = True,
    ) -> list[dict]:
        messages: list[dict] = [
            {"role": "system", "content": system_prompt},
        ]

        if include_image and self.img_as_llm_input and image is not None and self._supports_image_input():
            encoded_image, media_type = self.encode_image(image)
            messages.append(
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": user_prompt},
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": f"data:{media_type};base64,{encoded_image}",
                            },
                        },
                    ],
                }
            )
        else:
            messages.append({"role": "user", "content": user_prompt})

        return messages

    @staticmethod
    def _messages_include_image(messages: list[dict]) -> bool:
        for message in messages or []:
            content = message.get("content")
            if not isinstance(content, list):
                continue
            if any(isinstance(item, dict) and item.get("type") == "image_url" for item in content):
                return True
        return False

    @staticmethod
    def _is_probable_image_payload_error(exc: Exception) -> bool:
        text = str(exc).lower()
        return any(
            marker in text
            for marker in (
                "image",
                "vision",
                "multimodal",
                "content part",
                "unsupported content",
                "invalid chat format",
                "invalid request",
                "400",
                "422",
            )
        )

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

        messages = self._build_messages(user_prompt, system_prompt, image)

        payload = {
            "model": self.model,
            "messages": messages,
            "temperature": float(self.temperature),
            "top_p": float(self.top_p),
            "max_tokens": int(self.max_tokens),
            "presence_penalty" : 0.0,
            "frequency_penalty": 0.0,
            "repetition_penalty": float(self.repetition_penalty),
            "response_format": self._build_response_format(),
        }
        self._apply_no_thinking_options(payload)

        try:
            return self._make_api_request(payload)
        except RuntimeError as exc:
            if self._messages_include_image(messages) and self._is_probable_image_payload_error(exc):
                fallback_payload = dict(payload)
                fallback_payload["messages"] = self._build_messages(
                    user_prompt,
                    system_prompt,
                    image,
                    include_image=False,
                )
                return self._make_api_request(fallback_payload)
            raise

    def _apply_no_thinking_options(self, payload: dict) -> None:
        if self._is_lm_studio_backend():
            payload["reasoning"] = {"effort": "none"}
            return

        payload["chat_template_kwargs"] = {"enable_thinking": False}

    def _without_no_thinking_options(self, payload: dict) -> dict:
        fallback_payload = dict(payload)
        fallback_payload.pop("chat_template_kwargs", None)
        fallback_payload.pop("reasoning", None)
        return fallback_payload

    def _build_response_format(self) -> dict:
        if self._is_lm_studio_backend():
            # LM Studio accepts `text` and `json_schema`, but in practice
            # `text` is more stable here than forcing schema decoding.
            return {"type": "text"}
        return {"type": "json_object"}

    def _extract_message_text(self, message: dict) -> str:
        content = message.get("content")
        reasoning_content = message.get("reasoning_content")

        candidates = [content, reasoning_content]

        for candidate in candidates:
            if isinstance(candidate, str) and candidate.strip():
                return candidate.strip()

            if isinstance(candidate, list):
                parts = []
                for item in candidate:
                    if isinstance(item, dict) and item.get("type") == "text":
                        text = item.get("text")
                        if isinstance(text, str) and text.strip():
                            parts.append(text)
                joined = "\n".join(parts).strip()
                if joined:
                    return joined

        raise RuntimeError("Model returned no usable text in content or reasoning_content")

    def _make_api_request(self, payload):
        try:
            response = post_json_with_wsl_fallback(
                f"{self.api_base_url}/chat/completions",
                payload=payload,
                headers={"Content-Type": "application/json"},
                timeout=self.timeout,
            )

            response.raise_for_status()
            response_data = response.json()

            # --- TOKEN USAGE CAPTURE ---
            usage = response_data.get("usage")
            if usage:
                self.last_usage = usage
                logger = logging.getLogger(__name__)
                logger.debug(
                    "TOKENS | prompt=%s completion=%s total=%s",
                    usage.get("prompt_tokens"),
                    usage.get("completion_tokens"),
                    usage.get("total_tokens"),
                )

            choice = response_data["choices"][0]
            message = choice.get("message", {}) or {}
            content = self._extract_message_text(message)
            logger = logging.getLogger(__name__)
            logger.debug("LLM RESPONSE | %s", content)
            return content

        except requests.exceptions.RequestException as e:
            if (
                getattr(e, "response", None) is not None
                and e.response.status_code in (400, 422)
                and (
                    "chat_template_kwargs" in payload
                    or "reasoning" in payload
                )
            ):
                fallback_payload = self._without_no_thinking_options(payload)
                try:
                    response = post_json_with_wsl_fallback(
                        f"{self.api_base_url}/chat/completions",
                        payload=fallback_payload,
                        headers={"Content-Type": "application/json"},
                        timeout=self.timeout,
                    )
                    response.raise_for_status()
                    response_data = response.json()
                    usage = response_data.get("usage")
                    if usage:
                        self.last_usage = usage
                    choice = response_data["choices"][0]
                    message = choice.get("message", {}) or {}
                    return self._extract_message_text(message)
                except requests.exceptions.RequestException:
                    pass

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
            f"Translate to {target_lang}. "
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
