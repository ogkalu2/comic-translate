from types import SimpleNamespace

import numpy as np

from modules.ocr.processor import OCRProcessor
from modules.translation.llm.base import BaseLLMTranslation
from modules.translation.llm.custom import (
    CustomTranslation,
    LOCAL_VLLM_DEFAULT_API_BASE_URL,
    LOCAL_VLLM_DEFAULT_MODEL,
    LM_STUDIO_DEFAULT_API_BASE_URL,
    LM_STUDIO_DEFAULT_MODEL,
)
from modules.translation.llm.gpt import GPTTranslation
from modules.utils.translator_utils import (
    has_runaway_single_char_repetition,
    is_high_risk_sound_effect_text,
    sanitize_translation_source_text,
)


class _RetryLLM(BaseLLMTranslation):
    def __init__(self, responses):
        super().__init__()
        self.responses = list(responses)
        self.prompts = []
        self.target_lang = "English"

    def _perform_translation(self, user_prompt: str, system_prompt: str, image: np.ndarray) -> str:
        self.prompts.append(system_prompt)
        return self.responses.pop(0)


def test_sanitize_ocr_text_preserves_quotes_ellipsis_and_repeats():
    assert OCRProcessor.sanitize_ocr_text('  「はぁぁ…」  ') == "「はぁぁ…」"


def test_sanitize_translation_source_text_preserves_quotes_and_repeats():
    assert sanitize_translation_source_text('  "ааа..."  ') == '"ааа..."'


def test_llm_prompt_no_longer_forbids_repeat_characters():
    engine = _RetryLLM(['{"r":["ok"]}'])
    _, system_prompt = engine.build_translation_prompts(
        [SimpleNamespace(text='「はぁぁ…」')],
        "",
    )
    assert "no repeat characters" not in system_prompt
    assert "preserve tone, emotion, and punctuation" in system_prompt
    assert "native English speaker" in system_prompt
    assert "Avoid literal calques" in system_prompt
    assert "ensure correct agreement and inflection" in system_prompt
    assert "neutral or impersonal wording" in system_prompt
    assert "do not invent pseudo-words" in system_prompt


def test_llm_translation_retries_once_after_invalid_json():
    engine = _RetryLLM([
        '{"r":["аааааааааааааа',
        '{"r":["нормально"]}',
    ])
    blk = SimpleNamespace(text='「ааа」', translation="")

    result = engine.translate([blk], np.zeros((1, 1, 3), dtype=np.uint8), "")

    assert result[0].translation == "нормально"
    assert len(engine.prompts) == 2


def test_runaway_single_char_repetition_detection_is_targeted():
    assert has_runaway_single_char_repetition("А" * 20)
    assert not has_runaway_single_char_repetition("АААРРРГХХХ!!!")


def test_high_risk_sound_effect_detection_is_targeted():
    assert is_high_risk_sound_effect_text("AARRRGGGGGHHHHHH!")
    assert is_high_risk_sound_effect_text("ГРРРРХХХ!!!")
    assert not is_high_risk_sound_effect_text("ALL RIGHT PEOPLE, LISTEN UP!")


def test_llm_translation_retries_after_valid_json_with_runaway_repetition():
    engine = _RetryLLM([
        '{"r":["АААААААААААААААААААААА"]}',
        '{"r":["АРРРГХ!"]}',
    ])
    blk = SimpleNamespace(text="AARRRGGGGGHHHHHH!", translation="")

    result = engine.translate([blk], np.zeros((1, 1, 3), dtype=np.uint8), "")

    assert result[0].translation == "АРРРГХ!"
    assert len(engine.prompts) == 2


def test_llm_translation_falls_back_to_preserved_source_for_broken_interjection():
    engine = _RetryLLM([
        '{"r":["АААААААААААААААААААА',
        '{"r":["АААААААААААААААААААА!"]}',
    ])
    blk = SimpleNamespace(text="AARRRGGGGGHHHHHH!", translation="")

    result = engine.translate([blk], np.zeros((1, 1, 3), dtype=np.uint8), "")

    assert result[0].translation == "AARRRGGGGGHHHHHH!"


class _SplitLLM(BaseLLMTranslation):
    def __init__(self, responses):
        super().__init__()
        self.responses = list(responses)
        self.prompts = []
        self.target_lang = "English"
        self.source_lang = "Japanese"

    def _perform_translation(self, user_prompt: str, system_prompt: str, image: np.ndarray) -> str:
        self.prompts.append(system_prompt)
        return self.responses.pop(0)


def test_mixed_batch_translates_risky_interjection_separately():
    engine = _SplitLLM([
        '{"r":["Pay attention!","Move now!"]}',
        '{"r":["ARRGH!"]}',
    ])
    blocks = [
        SimpleNamespace(text="ALL RIGHT PEOPLE, LISTEN UP!", translation=""),
        SimpleNamespace(text="AARRRGGGGGHHHHHH!", translation=""),
        SimpleNamespace(text="MOVE!", translation=""),
    ]

    result = engine.translate(blocks, np.zeros((1, 1, 3), dtype=np.uint8), "")

    assert [blk.translation for blk in result] == ["Pay attention!", "ARRGH!", "Move now!"]
    assert len(engine.prompts) == 2


class _FakeSettings:
    def get_llm_settings(self):
        return {
            "image_input_enabled": False,
            "temperature": 0.1,
            "top_p": 0.95,
            "max_tokens": 512,
        }

    def get_credentials(self, _service):
        return {}

    @property
    def ui(self):
        return SimpleNamespace(tr=lambda value: value)


def test_gpt_translation_uses_configured_sampling_params(monkeypatch):
    engine = GPTTranslation()
    engine.initialize(_FakeSettings(), "Japanese", "English", "Custom")

    captured = {}

    def fake_make_api_request(payload):
        captured.update(payload)
        return '{"r":["ok"]}'

    monkeypatch.setattr(engine, "_make_api_request", fake_make_api_request)

    content = engine._perform_translation('["a"]', "sys", np.zeros((1, 1, 3), dtype=np.uint8))

    assert content == '{"r":["ok"]}'
    assert captured["temperature"] == 0.1
    assert captured["top_p"] == 0.95
    assert captured["frequency_penalty"] == 0.0
    assert captured["repetition_penalty"] == 1.05


def test_custom_translation_defaults_to_lm_studio_endpoint_and_model():
    engine = CustomTranslation()
    engine.initialize(_FakeSettings(), "Japanese", "English", "LM Studio")

    assert engine.api_base_url == LM_STUDIO_DEFAULT_API_BASE_URL
    assert engine.model == LM_STUDIO_DEFAULT_MODEL


class _CustomSettingsWithBareHost(_FakeSettings):
    def get_credentials(self, _service):
        return {
            "api_key": "",
            "api_url": "http://127.0.0.1:1234",
            "model": "qwen/qwen3.5-35b-a3b",
        }


def test_custom_translation_normalizes_bare_host_to_v1():
    engine = CustomTranslation()
    engine.initialize(_CustomSettingsWithBareHost(), "Japanese", "English", "Custom")

    assert engine.api_base_url == LM_STUDIO_DEFAULT_API_BASE_URL


def test_custom_translation_defaults_to_local_vllm_profile():
    engine = CustomTranslation()
    engine.initialize(_FakeSettings(), "Japanese", "English", "Local vLLM")

    assert engine.api_base_url == LOCAL_VLLM_DEFAULT_API_BASE_URL
    assert engine.model == LOCAL_VLLM_DEFAULT_MODEL


def test_gpt_translation_uses_lm_studio_json_schema_response_format():
    engine = GPTTranslation()
    engine.api_base_url = "http://127.0.0.1:1234/v1"

    response_format = engine._build_response_format()

    assert response_format == {"type": "text"}


def test_gpt_translation_uses_json_object_for_vllm():
    engine = GPTTranslation()
    engine.api_base_url = "http://127.0.0.1:8000/v1"

    response_format = engine._build_response_format()

    assert response_format == {"type": "json_object"}


class _FakeImageSettings(_FakeSettings):
    def get_llm_settings(self):
        return {
            "image_input_enabled": True,
            "temperature": 0.1,
            "top_p": 0.95,
            "max_tokens": 512,
        }


def test_gpt_translation_sends_image_to_lm_studio(monkeypatch):
    engine = GPTTranslation()
    engine.initialize(_FakeImageSettings(), "Japanese", "English", "Custom")
    engine.api_base_url = "http://127.0.0.1:1234/v1"
    engine.model = "qwen/qwen3.5-35b-a3b"

    captured = {}

    def fake_make_api_request(payload):
        captured.update(payload)
        return '{"r":["ok"]}'

    monkeypatch.setattr(engine, "_make_api_request", fake_make_api_request)

    content = engine._perform_translation("prompt", "system", np.zeros((2, 2, 3), dtype=np.uint8))

    assert content == '{"r":["ok"]}'
    assert captured["response_format"] == {"type": "text"}
    assert isinstance(captured["messages"][1]["content"], list)
    assert captured["messages"][1]["content"][0]["type"] == "text"
    assert captured["messages"][1]["content"][1]["type"] == "image_url"
    assert captured["messages"][1]["content"][1]["image_url"]["url"].startswith("data:image/")


def test_gpt_translation_sends_image_to_local_vllm_when_image_enabled(monkeypatch):
    engine = GPTTranslation()
    engine.initialize(_FakeImageSettings(), "Japanese", "English", "Custom")
    engine.api_base_url = "http://127.0.0.1:8000/v1"
    engine.model = "AxionML/Qwen3.5-35B-A3B-NVFP4"

    captured = {}

    def fake_make_api_request(payload):
        captured.update(payload)
        return '{"r":["ok"]}'

    monkeypatch.setattr(engine, "_make_api_request", fake_make_api_request)

    content = engine._perform_translation("prompt", "system", np.zeros((2, 2, 3), dtype=np.uint8))

    assert content == '{"r":["ok"]}'
    assert captured["response_format"] == {"type": "json_object"}
    assert isinstance(captured["messages"][1]["content"], list)
    assert captured["messages"][1]["content"][1]["type"] == "image_url"


def test_gpt_translation_retries_text_only_when_image_payload_is_rejected(monkeypatch):
    engine = GPTTranslation()
    engine.initialize(_FakeImageSettings(), "Japanese", "English", "Custom")
    engine.api_base_url = "http://127.0.0.1:8000/v1"
    engine.model = "text-only-model"
    calls = []

    def fake_make_api_request(payload):
        calls.append(payload)
        if isinstance(payload["messages"][1]["content"], list):
            raise RuntimeError("400 invalid request: image content is unsupported")
        return '{"r":["ok"]}'

    monkeypatch.setattr(engine, "_make_api_request", fake_make_api_request)

    content = engine._perform_translation("prompt", "system", np.zeros((2, 2, 3), dtype=np.uint8))

    assert content == '{"r":["ok"]}'
    assert isinstance(calls[0]["messages"][1]["content"], list)
    assert isinstance(calls[1]["messages"][1]["content"], str)


class _InterpretLLM(BaseLLMTranslation):
    def __init__(self, responses):
        super().__init__()
        self.responses = list(responses)
        self.user_prompts = []
        self.target_lang = "English"
        self.source_lang = "Japanese"
        self.interpret_then_translate = True
        self.use_scene_memory = True

    def _perform_translation(self, user_prompt: str, system_prompt: str, image: np.ndarray) -> str:
        self.user_prompts.append(user_prompt)
        return self.responses.pop(0)


def test_interpret_then_translate_adds_internal_context_and_scene_memory():
    engine = _InterpretLLM(
        [
            '{"i":["Speaker is being sarcastic but not hostile."],"m":"Light sarcasm between familiar speakers."}',
            '{"r":["Sure, very funny."]}',
        ]
    )
    blk = SimpleNamespace(text="はいはい", translation="")

    result = engine.translate([blk], np.zeros((1, 1, 3), dtype=np.uint8), "Previous page context here.")

    assert result[0].translation == "Sure, very funny."
    assert len(engine.user_prompts) == 2
    assert "Previous page context here." in engine.user_prompts[0]
    assert "Current page meaning notes" in engine.user_prompts[1]
    assert "Speaker is being sarcastic but not hostile." in engine.user_prompts[1]
    assert engine.last_scene_memory == "Light sarcasm between familiar speakers."


def test_interpret_then_translate_retries_when_interpretation_count_is_wrong():
    engine = _InterpretLLM(
        [
            '{"i":["Only the first note."],"m":"Partial memory."}',
            '{"i":["First line meaning.","Second line meaning."],"m":"Repaired memory."}',
            '{"r":["First.","Second."]}',
        ]
    )
    blocks = [
        SimpleNamespace(text="一つ目", translation=""),
        SimpleNamespace(text="二つ目", translation=""),
    ]

    result = engine.translate(blocks, np.zeros((1, 1, 3), dtype=np.uint8), "")

    assert [blk.translation for blk in result] == ["First.", "Second."]
    assert len(engine.user_prompts) == 3
    assert "Current page meaning notes" in engine.user_prompts[2]
    assert "First line meaning." in engine.user_prompts[2]
    assert "Second line meaning." in engine.user_prompts[2]
    assert engine.last_scene_memory == "Repaired memory."


def test_interpret_then_translate_normalizes_wrong_count_after_retry():
    engine = _InterpretLLM(
        [
            '{"i":["Only the first note."],"m":"Partial memory."}',
            '{"i":["Still only first."],"m":"Fallback memory."}',
            '{"r":["First.","Second."]}',
        ]
    )
    blocks = [
        SimpleNamespace(text="一つ目", translation=""),
        SimpleNamespace(text="二つ目", translation=""),
    ]

    result = engine.translate(blocks, np.zeros((1, 1, 3), dtype=np.uint8), "")

    assert [blk.translation for blk in result] == ["First.", "Second."]
    assert len(engine.user_prompts) == 3
    assert "Still only first." in engine.user_prompts[2]
    assert "ambiguous from available context" in engine.user_prompts[2]
    assert engine.last_scene_memory == "Fallback memory."


def test_single_block_translation_joins_split_output_after_repair_retry():
    engine = _InterpretLLM(
        [
            '{"r":["part one","part two"]}',
            '{"r":["part one","part two"]}',
        ]
    )
    engine.interpret_then_translate = False
    engine.use_scene_memory = False
    block = SimpleNamespace(text="一つの吹き出し", translation="")

    result = engine.translate([block], np.zeros((1, 1, 3), dtype=np.uint8), "Previous page has two lines.")

    assert result[0].translation == "part one part two"
    assert len(engine.user_prompts) == 2
