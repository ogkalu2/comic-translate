from types import SimpleNamespace

import numpy as np

from modules.ocr.factory import OCRFactory
from modules.ocr.ppocr.engine2 import (
    HUNYUAN_OCR_LM_STUDIO_DEFAULT_API_BASE_URL,
    HUNYUAN_OCR_LM_STUDIO_DEFAULT_MODEL,
    HUNYUAN_OCR_LOCAL_VLLM_DEFAULT_API_BASE_URL,
    HUNYUAN_OCR_LOCAL_VLLM_DEFAULT_MODEL,
)
from modules.ocr.processor import OCRProcessor
from pipeline.cache_manager import CacheManager


def test_default_ocr_factory_uses_language_hint_groups(monkeypatch):
    marker = object()

    monkeypatch.setattr(
        OCRFactory,
        "_create_manga_ocr",
        staticmethod(lambda settings, backend="onnx": ("manga", backend, marker)),
    )
    monkeypatch.setattr(
        OCRFactory,
        "_create_pororo_ocr",
        staticmethod(lambda settings, backend="onnx": ("pororo", backend, marker)),
    )
    monkeypatch.setattr(
        OCRFactory,
        "_create_ppocr",
        staticmethod(lambda settings, lang, backend="onnx": ("ppocr", lang, backend, marker)),
    )

    assert OCRFactory._create_new_engine(marker, "Japanese", "Default") == ("manga", "onnx", marker)
    assert OCRFactory._create_new_engine(marker, "Korean", "Default") == ("pororo", "onnx", marker)
    assert OCRFactory._create_new_engine(marker, "Other Languages", "Default") == (
        "ppocr",
        "latin",
        "onnx",
        marker,
    )


def test_ocr_processor_uses_main_page_hint_when_callers_pass_empty(monkeypatch):
    captured = {}

    def fake_create_engine(settings, source_lang_english, ocr_key, backend="onnx"):
        captured["settings"] = settings
        captured["source_lang_english"] = source_lang_english
        captured["ocr_key"] = ocr_key
        captured["backend"] = backend
        return object()

    monkeypatch.setattr(OCRFactory, "create_engine", fake_create_engine)

    settings_page = SimpleNamespace(
        get_tool_selection=lambda name: "Default" if name == "ocr" else None,
        ui=SimpleNamespace(tr=lambda value: value),
    )
    main_page = SimpleNamespace(
        settings_page=settings_page,
        get_ocr_language_hint=lambda: "Korean",
        lang_mapping={},
    )

    processor = OCRProcessor()
    processor.initialize(main_page, "")
    processor.get_engine()

    assert captured["settings"] is settings_page
    assert captured["source_lang_english"] == "Korean"
    assert captured["ocr_key"] == "Default"
    assert captured["backend"] == "onnx"


def test_ocr_cache_key_includes_language_hint():
    image = np.zeros((16, 16, 3), dtype=np.uint8)
    cache_manager = CacheManager()

    japanese_key = cache_manager._get_ocr_cache_key(image, "Japanese", "Default", "cpu")
    korean_key = cache_manager._get_ocr_cache_key(image, "Korean", "Default", "cpu")
    other_key = cache_manager._get_ocr_cache_key(image, "Other Languages", "Default", "cpu")

    assert japanese_key != korean_key
    assert korean_key != other_key
    assert japanese_key != other_key


def test_hunyuan_ocr_factory_uses_local_vllm_profile_by_default(monkeypatch):
    captured = {}

    class _FakeHunyuanEngine:
        def initialize(self, **kwargs):
            captured.update(kwargs)

    monkeypatch.setattr("modules.ocr.factory.HunyuanOCREngine", _FakeHunyuanEngine)

    settings = SimpleNamespace(
        get_tool_selection=lambda name: None,
        get_batch_settings=lambda: {"ocr_batch_size": 5},
        ui=SimpleNamespace(tr=lambda value: value),
    )

    engine = OCRFactory._create_hunyuan_ocr(settings)

    assert isinstance(engine, _FakeHunyuanEngine)
    assert captured["url"] == HUNYUAN_OCR_LOCAL_VLLM_DEFAULT_API_BASE_URL
    assert captured["model"] == HUNYUAN_OCR_LOCAL_VLLM_DEFAULT_MODEL
    assert captured["recognition_batch_size"] == 5


def test_hunyuan_ocr_factory_uses_lm_studio_profile(monkeypatch):
    captured = {}

    class _FakeHunyuanEngine:
        def initialize(self, **kwargs):
            captured.update(kwargs)

    monkeypatch.setattr("modules.ocr.factory.HunyuanOCREngine", _FakeHunyuanEngine)

    settings = SimpleNamespace(
        get_tool_selection=lambda name: "LM Studio" if name == "hunyuanocr_backend" else None,
        get_batch_settings=lambda: {"ocr_batch_size": 7},
        ui=SimpleNamespace(tr=lambda value: value),
    )

    engine = OCRFactory._create_hunyuan_ocr(settings)

    assert isinstance(engine, _FakeHunyuanEngine)
    assert captured["url"] == HUNYUAN_OCR_LM_STUDIO_DEFAULT_API_BASE_URL
    assert captured["model"] == HUNYUAN_OCR_LM_STUDIO_DEFAULT_MODEL
    assert captured["recognition_batch_size"] == 7


def test_hunyuan_ocr_factory_accepts_backend_specific_key(monkeypatch):
    marker = object()

    monkeypatch.setattr(
        OCRFactory,
        "_create_hunyuan_ocr",
        staticmethod(lambda settings: ("hunyuan", marker)),
    )

    assert OCRFactory._create_new_engine(marker, "Japanese", "Tencent/HunyuanOCR [LM Studio]") == (
        "hunyuan",
        marker,
    )


def test_ocr_processor_includes_hunyuan_backend_in_key():
    settings_page = SimpleNamespace(
        get_tool_selection=lambda name: {
            "ocr": "Tencent/HunyuanOCR",
            "hunyuanocr_backend": "LM Studio",
        }.get(name),
        ui=SimpleNamespace(tr=lambda value: value),
    )
    main_page = SimpleNamespace(
        settings_page=settings_page,
        get_ocr_language_hint=lambda: "English",
        lang_mapping={},
    )

    processor = OCRProcessor()
    processor.initialize(main_page, "")

    assert processor.ocr_key == "Tencent/HunyuanOCR [LM Studio]"
