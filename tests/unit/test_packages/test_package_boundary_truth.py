import importlib
import importlib.util
import tomllib
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[3]


def load_pyproject(path: str) -> dict:
    with (REPO_ROOT / path).open("rb") as handle:
        return tomllib.load(handle)


def test_package_roots_do_not_eagerly_export_monolith_backed_concrete_types():
    detection = importlib.import_module("comic_translate_detection")
    ocr = importlib.import_module("comic_translate_ocr")
    translation = importlib.import_module("comic_translate_translation")
    rendering = importlib.import_module("comic_translate_rendering")
    adapters = importlib.import_module("comic_translate_core.adapters")

    assert not hasattr(detection, "PanelDetector")
    assert not hasattr(detection, "BubbleDetector")
    assert not hasattr(ocr, "OCREngineFactory")
    assert not hasattr(translation, "TranslationEngineFactory")
    assert not hasattr(rendering, "RenderingEngineFactory")
    assert not hasattr(rendering, "InpaintingEngineFactory")
    assert not hasattr(adapters, "OCRAdapter")
    assert not hasattr(adapters, "TranslationAdapter")
    assert not hasattr(adapters, "RenderingAdapter")


def test_qa_root_provider_surface_only_exports_base_contract():
    providers = importlib.import_module("comic_translate_qa.providers")

    assert providers.__all__ == ["BaseQAProvider"]


def test_qa_pyproject_does_not_publish_base_install_script_lie():
    pyproject = load_pyproject("packages/qa/pyproject.toml")

    assert "scripts" not in pyproject["project"]


def test_qa_pyproject_declares_provider_extras_explicitly():
    pyproject = load_pyproject("packages/qa/pyproject.toml")
    optional = pyproject["project"]["optional-dependencies"]

    assert "openai" in optional
    assert "anthropic" in optional


def test_translation_factory_gpt_mapping_resolves_to_real_class():
    module = importlib.import_module("comic_translate_translation.engine")

    engine = module.TranslationEngineFactory.create_engine("gpt")

    assert engine.__class__.__name__ == "GPTTranslation"


def test_explicit_bridge_modules_remain_importable():
    assert importlib.util.find_spec("comic_translate_detection.detector") is not None
    assert importlib.util.find_spec("comic_translate_ocr.engine") is not None
    assert importlib.util.find_spec("comic_translate_translation.engine") is not None
    assert importlib.util.find_spec("comic_translate_rendering.engine") is not None
    assert importlib.util.find_spec("comic_translate_core.adapters.ocr") is not None
