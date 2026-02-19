from dataclasses import dataclass, field
from typing import List
import itertools

@dataclass
class ProviderConfig:
    name: str
    base_url: str
    api_keys: List[str]
    free_models: List[str]
    paid_models: List[str]
    rate_limit_rpm: int = 60

DEFAULT_PROVIDERS: List[ProviderConfig] = [
    ProviderConfig(
        name="openrouter",
        base_url="https://openrouter.ai/api/v1",
        api_keys=[],
        free_models=[
            "mistralai/mistral-7b-instruct:free",
            "meta-llama/llama-3-8b-instruct:free",
        ],
        paid_models=["anthropic/claude-3-haiku", "openai/gpt-4o-mini"],
        rate_limit_rpm=60,
    ),
]

TRANSLATION_PRIORITY = [
    ("openrouter", "free"),
    ("openrouter", "paid"),
]

class KeyRotator:
    def __init__(self):
        self._cycles: dict = {}

    def next_key(self, provider_name: str, keys: List[str]) -> str:
        if not keys:
            return ""
        if provider_name not in self._cycles:
            self._cycles[provider_name] = itertools.cycle(keys)
        return next(self._cycles[provider_name])
