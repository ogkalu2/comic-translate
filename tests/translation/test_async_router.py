import pytest
import asyncio
from modules.translation.async_router import AsyncTranslationRouter, TranslationResult

def test_result_success():
    r = TranslationResult(text="你好", model="free-model", provider="openrouter", status="success")
    assert r.is_success()

def test_result_failed():
    r = TranslationResult(text="Hello", model="", provider="", status="api_failed")
    assert not r.is_success()

def test_router_returns_success_on_first_provider():
    router = AsyncTranslationRouter()

    async def fake_call(base_url, api_key, model, text, src, tgt):
        return "你好"

    router._call_api = fake_call
    result = asyncio.run(router.translate("Hello", "en", "zh-hk"))
    assert result.status == "success"
    assert result.text == "你好"

def test_router_falls_back_on_failure():
    router = AsyncTranslationRouter()
    call_count = 0

    async def fake_call(base_url, api_key, model, text, src, tgt):
        nonlocal call_count
        call_count += 1
        if call_count < 2:
            raise Exception("rate limit")
        return "你好"

    router._call_api = fake_call
    result = asyncio.run(router.translate("Hello", "en", "zh-hk"))
    assert result.status == "success"
    assert call_count == 2
