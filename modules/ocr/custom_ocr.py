import numpy as np
import requests
import json

from .base import OCREngine
from ..utils.textblock import TextBlock, adjust_text_line_coordinates


class CustomOCR(OCREngine):
    """OCR engine using a custom OpenAI-compatible vision API endpoint.

    The user supplies their own API base URL, API key (optional for local
    servers) and model name. Any server that exposes an OpenAI-compatible
    ``/chat/completions`` endpoint with vision support can be used, e.g.
    Ollama, LM Studio, vLLM, or cloud providers.
    """

    DEFAULT_API_URL = "http://localhost:11434/v1"

    def __init__(self):
        self.api_key = ""
        self.model = ""
        self.api_base_url = f"{self.DEFAULT_API_URL}/chat/completions"
        self.expansion_percentage = 0
        self.max_tokens = 5000

    def initialize(
        self,
        api_key: str = "",
        api_url: str = DEFAULT_API_URL,
        model: str = "",
        expansion_percentage: int = 0,
    ) -> None:
        """Initialize the custom OCR engine.

        Args:
            api_key: API key for the endpoint (empty for local servers).
            api_url: Base API URL, e.g. ``http://localhost:11434/v1``.
                ``/chat/completions`` is appended automatically if missing.
            model: Model name as exposed by the endpoint.
            expansion_percentage: Percentage to expand text bounding boxes.
        """
        self.api_key = api_key or ""
        self.model = model or ""
        self.expansion_percentage = expansion_percentage

        base = (api_url or self.DEFAULT_API_URL).rstrip("/")
        if base.endswith("/chat/completions"):
            self.api_base_url = base
        else:
            self.api_base_url = f"{base}/chat/completions"

    def process_image(self, img: np.ndarray, blk_list: list[TextBlock]) -> list[TextBlock]:
        """Process an image with the custom OCR by processing individual text regions."""
        for blk in blk_list:
            if blk.bubble_xyxy is not None:
                x1, y1, x2, y2 = blk.bubble_xyxy
            else:
                x1, y1, x2, y2 = adjust_text_line_coordinates(
                    blk.xyxy,
                    self.expansion_percentage,
                    self.expansion_percentage,
                    img,
                )

            if x1 < x2 and y1 < y2 and x1 >= 0 and y1 >= 0 and x2 <= img.shape[1] and y2 <= img.shape[0]:
                cropped_img = img[y1:y2, x1:x2]
                img_to_ocr = self.encode_image(cropped_img)
                blk.text = self._get_ocr(img_to_ocr)

        return blk_list

    def _get_ocr(self, base64_image: str) -> str:
        """Get OCR result from the custom vision model via REST API call."""
        if not self.model:
            raise ValueError("Model not initialized. Call initialize() first.")

        headers = {
            "Content-Type": "application/json",
        }
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"

        payload = {
            "model": self.model,
            "messages": [
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "text",
                            "text": "Write out the text in this image. Do NOT Translate. Do not write anything else",
                        },
                        {
                            "type": "image_url",
                            "image_url": {"url": f"data:image/jpeg;base64,{base64_image}"},
                        },
                    ],
                }
            ],
            "max_completion_tokens": self.max_tokens,
        }

        try:
            response = requests.post(
                self.api_base_url,
                headers=headers,
                data=json.dumps(payload),
                timeout=60,
            )
            response.raise_for_status()
        except requests.exceptions.RequestException as e:
            error_msg = f"Custom OCR API request failed: {str(e)}"
            detail = ""
            if hasattr(e, "response") and e.response is not None:
                try:
                    error_details = e.response.json()
                    detail = json.dumps(error_details)
                    error_msg += f" - {detail}"
                except Exception:
                    error_msg += f" - Status code: {e.response.status_code}"
            lowered = (str(e) + detail).lower()
            if "multimodal" in lowered or "does not support" in lowered or "invalid_request_error" in lowered:
                error_msg += (
                    "\nHint: the selected model likely does not support image (vision) "
                    "input. Choose a vision-capable model (e.g. llama3.2-vision for Ollama, "
                    "llava, qwen2.5-vl, etc.)."
                )
            print(error_msg)
            return ""

        response_json = response.json()
        text = response_json["choices"][0]["message"]["content"]
        return text.replace("\n", " ") if "\n" in text else text
