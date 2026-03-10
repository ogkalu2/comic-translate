import asyncio
import json
import urllib.request
from dataclasses import dataclass
from typing import Optional, List
from modules.translation.provider_config import (
    DEFAULT_PROVIDERS, TRANSLATION_PRIORITY, KeyRotator, ProviderConfig
)

@dataclass
class TranslationResult:
    text: str
    model: str
    provider: str
    status: str  # "success" | "api_failed"

    def is_success(self) -> bool:
        return self.status == "success"

class AsyncTranslationRouter:
    def __init__(self, providers: Optional[List[ProviderConfig]] = None):
        self.providers = {p.name: p for p in (providers or DEFAULT_PROVIDERS)}
        self._rotator = KeyRotator()
        self._semaphore = asyncio.Semaphore(10)

    async def _call_api(self, base_url: str, api_key: str, model: str,
                        text: str, src: str, tgt: str) -> str:
        payload = json.dumps({
            "model": model,
            "messages": [
                {"role": "system", "content": f"Translate from {src} to {tgt}. Return only the translation."},
                {"role": "user", "content": text},
            ],
            "max_tokens": 500,
        }).encode()
        req = urllib.request.Request(
            f"{base_url}/chat/completions",
            data=payload,
            headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
        )
        loop = asyncio.get_event_loop()
        def _do_request():
            with urllib.request.urlopen(req, timeout=30) as resp:
                return json.loads(resp.read())
        data = await loop.run_in_executor(None, _do_request)
        return data["choices"][0]["message"]["content"].strip()

    async def translate(self, text: str, src: str, tgt: str) -> TranslationResult:
        async with self._semaphore:
            for provider_name, tier in TRANSLATION_PRIORITY:
                provider = self.providers.get(provider_name)
                if not provider:
                    continue
                models = provider.free_models if tier == "free" else provider.paid_models
                api_key = self._rotator.next_key(provider_name, provider.api_keys)
                for model in models:
                    try:
                        result = await self._call_api(
                            provider.base_url, api_key, model, text, src, tgt
                        )
                        return TranslationResult(
                            text=result, model=model,
                            provider=provider_name, status="success"
                        )
                    except Exception:
                        continue
            return TranslationResult(text=text, model="", provider="", status="api_failed")

    async def translate_batch(
        self, texts: List[str], src: str, tgt: str
    ) -> List[TranslationResult]:
        tasks = [self.translate(t, src, tgt) for t in texts]
        return await asyncio.gather(*tasks)
