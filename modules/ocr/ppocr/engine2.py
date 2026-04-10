from __future__ import annotations

import base64
import json
import re
from concurrent.futures import ThreadPoolExecutor, as_completed
from io import BytesIO
from typing import List

import numpy as np
import requests
from PIL import Image

from modules.ocr.base import OCREngine
from modules.ocr.crop_utils import extract_block_crops
from modules.utils.local_vllm import post_json_with_wsl_fallback
from modules.utils.textblock import TextBlock


class VLLMOcrClient:
    MAX_PREPARED_LONG_SIDE = 512
    MAX_PREPARED_AREA = 256 * 256
    MIN_PREPARED_SIDE = 64

    def __init__(self, url: str = "http://127.0.0.1:8001/v1", model: str = "hunyuanocr", timeout: int = 300):
        self.url = url.rstrip("/")
        self.model = model
        self.timeout = timeout

    def _img_to_data_url(self, pil_img: Image.Image, fmt: str = "PNG") -> str:
        buf = BytesIO()
        pil_img.save(buf, format=fmt)
        b64 = base64.b64encode(buf.getvalue()).decode("ascii")
        return f"data:image/{fmt.lower()};base64,{b64}"

    def _extract_json_or_text(self, content: str) -> str:
        if content is None:
            return ""
        text = content.strip()
        if not text:
            return ""

        if text.startswith("```"):
            text = re.sub(
                r"^```(?:json)?\s*|\s*```$",
                "",
                text,
                flags=re.IGNORECASE | re.DOTALL,
            ).strip()

        if text.startswith("{") and text.endswith("}"):
            try:
                obj = json.loads(text)
                if isinstance(obj, dict):
                    value = obj.get("text", "")
                    return value.strip() if isinstance(value, str) else str(value)
            except json.JSONDecodeError:
                pass

        match = re.search(r"\{.*\}", text, flags=re.DOTALL)
        if match:
            try:
                obj = json.loads(match.group(0))
                if isinstance(obj, dict):
                    value = obj.get("text", "")
                    return value.strip() if isinstance(value, str) else str(value)
            except json.JSONDecodeError:
                pass

        return text

    def _prepare_image(self, img: Image.Image) -> Image.Image:
        prepared = img.convert("RGB")
        width, height = prepared.size
        if width <= 0 or height <= 0:
            return prepared

        long_side = max(width, height)
        area = width * height

        scale_by_side = 1.0
        if long_side > self.MAX_PREPARED_LONG_SIDE:
            scale_by_side = self.MAX_PREPARED_LONG_SIDE / float(long_side)

        scale_by_area = 1.0
        if area > self.MAX_PREPARED_AREA:
            scale_by_area = (self.MAX_PREPARED_AREA / float(area)) ** 0.5

        scale = min(1.0, scale_by_side, scale_by_area)
        if scale >= 0.999:
            return prepared

        resized_width = max(self.MIN_PREPARED_SIDE, int(round(width * scale)))
        resized_height = max(self.MIN_PREPARED_SIDE, int(round(height * scale)))
        return prepared.resize((resized_width, resized_height), Image.Resampling.LANCZOS)

    def _build_payload(self, pil_img: Image.Image) -> dict:
        prepared_img = self._prepare_image(pil_img)
        data_url = self._img_to_data_url(prepared_img, "PNG")
        return {
            "model": self.model,
            "temperature": 0.0,
            "messages": [
                {"role": "system", "content": ""},
                {
                    "role": "user",
                    "content": [
                        {"type": "image_url", "image_url": {"url": data_url}},
                        {"type": "text", "text": "提取图中的文字"},
                    ],
                },
            ],
            "top_k": 1,
            "max_tokens": 128,
            "repetition_penalty": 1.0,
        }

    def ocr_one(self, pil_img: Image.Image) -> str:
        payload = self._build_payload(pil_img)
        response = post_json_with_wsl_fallback(
            f"{self.url}/chat/completions",
            payload=payload,
            timeout=self.timeout,
        )
        if response.status_code != 200:
            raise RuntimeError(f"vLLM HTTP {response.status_code}: {response.text}")

        content = response.json()["choices"][0]["message"]["content"]
        return self._extract_json_or_text(content)

    def ocr_many(self, pil_images: List[Image.Image], max_concurrency: int = 8) -> list[str]:
        if not pil_images:
            return []

        concurrency = max(1, int(max_concurrency))
        results = [""] * len(pil_images)
        with ThreadPoolExecutor(max_workers=concurrency) as executor:
            future_to_index = {
                executor.submit(self.ocr_one, image): index
                for index, image in enumerate(pil_images)
            }
            for future in as_completed(future_to_index):
                index = future_to_index[future]
                results[index] = future.result()
        return results


class HunyuanOCREngine(OCREngine):
    def __init__(self):
        self.client = VLLMOcrClient()
        self.expansion_percentage = 5
        self.recognition_batch_size = 32

    def initialize(
        self,
        url: str = "http://127.0.0.1:8001/v1",
        model: str = "hunyuanocr",
        timeout: int = 300,
        expansion_percentage: int = 5,
        recognition_batch_size: int = 32,
        **kwargs,
    ) -> None:
        self.client = VLLMOcrClient(url=url, model=model, timeout=timeout)
        self.expansion_percentage = expansion_percentage
        self.recognition_batch_size = max(1, int(recognition_batch_size))

    def supports_crop_batching(self) -> bool:
        return True

    def supports_block_crop_batching(self) -> bool:
        return True

    def process_crops(
        self,
        crops: list[np.ndarray],
        batch_size: int | None = None,
    ) -> tuple[list[str], list[float]]:
        pil_images = [
            crop if isinstance(crop, Image.Image) else Image.fromarray(crop)
            for crop in crops
        ]
        texts = self.client.ocr_many(
            pil_images,
            max_concurrency=batch_size or self.recognition_batch_size,
        )
        confs = [1.0 if text else 0.0 for text in texts]
        return texts, confs

    def process_image(self, img: np.ndarray, blk_list: list[TextBlock]) -> list[TextBlock]:
        crop_records, invalid_indices = extract_block_crops(
            img,
            blk_list,
            expansion_percentage=self.expansion_percentage,
        )
        for block_index in invalid_indices:
            blk_list[block_index].text = ""

        if not crop_records:
            return blk_list

        texts, _ = self.process_crops(
            [record.crop for record in crop_records],
            batch_size=self.recognition_batch_size,
        )
        for record, text in zip(crop_records, texts):
            blk_list[record.block_index].text = text
        return blk_list
