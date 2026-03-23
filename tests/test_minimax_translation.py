"""Unit tests for MiniMax translation provider integration."""

import json
import os
import sys
import types
import unittest
from unittest.mock import MagicMock, patch

import numpy as np


# ---------------------------------------------------------------------------
# Mock heavy dependencies that are not available in CI/test environments
# ---------------------------------------------------------------------------

def _install_mock_modules():
    """Pre-install stub modules so the project's imports succeed."""
    stubs = [
        "mahotas", "mahotas.features", "mahotas.features.texture",
        "jieba", "janome", "janome.tokenizer",
        "pythainlp", "pythainlp.tokenize",
        "jaconv",
        "pdfplumber", "py7zr", "rarfile", "img2pdf", "keyring",
        "shapely", "pyclipper", "onnxruntime",
        "wget", "msgpack",
    ]
    for name in stubs:
        if name not in sys.modules:
            sys.modules[name] = types.ModuleType(name)

    # PySide6 needs deep attribute access (Qt, Signal, QSettings, etc.)
    # Use a single MagicMock() so all sub-attribute chains resolve.
    pyside_mock = MagicMock()
    pyside_names = [
        "PySide6", "PySide6.QtWidgets", "PySide6.QtCore", "PySide6.QtGui",
        "PySide6.QtSvg", "PySide6.QtSvgWidgets", "PySide6.QtNetwork",
        "PySide6.QtMultimedia", "PySide6.QtOpenGL",
    ]
    for name in pyside_names:
        if name not in sys.modules:
            sys.modules[name] = pyside_mock

    # imkit needs encode_image
    imkit_mod = types.ModuleType("imkit")
    imkit_mod.encode_image = lambda img, fmt: b"\x00"
    # Add sub-modules that imkit/__init__.py tries to import
    for sub in ("transforms", "io", "draw", "color", "morphology",
                "geometry", "filters", "features"):
        full = f"imkit.{sub}"
        if full not in sys.modules:
            sys.modules[full] = types.ModuleType(full)
    sys.modules["imkit"] = imkit_mod

    # jieba.cut
    sys.modules["jieba"].cut = lambda *a, **kw: []

    # janome tokenizer
    tok_mod = sys.modules["janome.tokenizer"]
    tok_mod.Tokenizer = MagicMock

    # pythainlp word_tokenize
    sys.modules["pythainlp.tokenize"].word_tokenize = lambda *a, **kw: []


_install_mock_modules()


# Now it's safe to import project modules
from modules.translation.llm.minimax import MinimaxTranslation  # noqa: E402
from modules.translation.llm.gpt import GPTTranslation  # noqa: E402
from modules.translation.llm.base import BaseLLMTranslation  # noqa: E402
from modules.translation.base import LLMTranslation  # noqa: E402
from modules.utils.translator_utils import MODEL_MAP  # noqa: E402


# ---------------------------------------------------------------------------
# Unit Tests
# ---------------------------------------------------------------------------

class TestMinimaxTranslationInit(unittest.TestCase):
    """Test MinimaxTranslation class initialization and attributes."""

    def test_default_api_base_url(self):
        engine = MinimaxTranslation()
        self.assertEqual(engine.api_base_url, "https://api.minimax.io/v1")

    def test_supports_images(self):
        engine = MinimaxTranslation()
        self.assertTrue(engine.supports_images)

    def test_inherits_gpt_translation(self):
        engine = MinimaxTranslation()
        self.assertIsInstance(engine, GPTTranslation)

    def test_inherits_base_llm_translation(self):
        engine = MinimaxTranslation()
        self.assertIsInstance(engine, BaseLLMTranslation)

    def test_inherits_llm_translation_interface(self):
        engine = MinimaxTranslation()
        self.assertIsInstance(engine, LLMTranslation)


class TestMinimaxTranslationInitialize(unittest.TestCase):
    """Test MinimaxTranslation.initialize() credential loading."""

    def _mock_settings(self, api_key="test-key-123"):
        settings = MagicMock()
        settings.ui.tr.side_effect = lambda x: x
        settings.get_llm_settings.return_value = {"image_input_enabled": True}
        settings.get_credentials.return_value = {"api_key": api_key}
        return settings

    def test_initialize_sets_api_key(self):
        engine = MinimaxTranslation()
        settings = self._mock_settings("mm-api-key-xyz")
        engine.initialize(settings, "English", "Chinese", "MiniMax-M2.7")
        self.assertEqual(engine.api_key, "mm-api-key-xyz")

    def test_initialize_sets_model_from_map(self):
        engine = MinimaxTranslation()
        settings = self._mock_settings()
        engine.initialize(settings, "English", "Japanese", "MiniMax-M2.7")
        self.assertEqual(engine.model, "MiniMax-M2.7")

    def test_initialize_sets_languages(self):
        engine = MinimaxTranslation()
        settings = self._mock_settings()
        engine.initialize(settings, "English", "Korean", "MiniMax-M2.7")
        self.assertEqual(engine.source_lang, "English")
        self.assertEqual(engine.target_lang, "Korean")

    def test_initialize_preserves_api_base_url(self):
        engine = MinimaxTranslation()
        settings = self._mock_settings()
        engine.initialize(settings, "English", "French", "MiniMax-M2.7")
        self.assertEqual(engine.api_base_url, "https://api.minimax.io/v1")

    def test_initialize_calls_get_credentials_with_minimax(self):
        engine = MinimaxTranslation()
        settings = self._mock_settings()
        engine.initialize(settings, "English", "Spanish", "MiniMax-M2.7")
        settings.get_credentials.assert_called_once_with("MiniMax")

    def test_initialize_highspeed_model(self):
        engine = MinimaxTranslation()
        settings = self._mock_settings()
        engine.initialize(settings, "English", "German", "MiniMax-M2.7-highspeed")
        self.assertEqual(engine.model, "MiniMax-M2.7-highspeed")


class TestModelMap(unittest.TestCase):
    """Test that MODEL_MAP contains MiniMax entries."""

    def test_minimax_m27_in_model_map(self):
        self.assertIn("MiniMax-M2.7", MODEL_MAP)
        self.assertEqual(MODEL_MAP["MiniMax-M2.7"], "MiniMax-M2.7")

    def test_minimax_m27_highspeed_in_model_map(self):
        self.assertIn("MiniMax-M2.7-highspeed", MODEL_MAP)
        self.assertEqual(MODEL_MAP["MiniMax-M2.7-highspeed"], "MiniMax-M2.7-highspeed")


def _import_factory():
    """Import TranslationFactory with heavy UI deps mocked out."""
    # Pre-mock the modules that pull in the full PySide6 widget tree
    for mod_name in (
        "app.ui.settings.settings_page",
        "app.ui.settings.settings_ui",
        "app.ui.dayu_widgets",
        "app.ui.dayu_widgets.clickable_card",
        "app.ui.dayu_widgets.divider",
        "app.ui.dayu_widgets.qt",
        "app.ui.dayu_widgets.theme",
        "app.ui.dayu_widgets.utils",
        "app.account.auth.token_storage",
        "app.account.auth.auth_client",
        "app.account.config",
        "app.update_checker",
        "modules.translation.user",
    ):
        if mod_name not in sys.modules:
            sys.modules[mod_name] = MagicMock()

    # Provide a real get_token that returns None (no user logged in)
    gt_mod = types.ModuleType("app.account.auth.token_storage")
    gt_mod.get_token = lambda *a, **kw: None
    sys.modules["app.account.auth.token_storage"] = gt_mod

    from modules.translation.factory import TranslationFactory
    return TranslationFactory


class TestTranslationFactory(unittest.TestCase):
    """Test that TranslationFactory recognizes MiniMax engines."""

    @classmethod
    def setUpClass(cls):
        cls.Factory = _import_factory()

    def test_minimax_in_llm_engine_identifiers(self):
        self.assertIn("MiniMax", self.Factory.LLM_ENGINE_IDENTIFIERS)

    def test_minimax_maps_to_correct_class(self):
        self.assertIs(
            self.Factory.LLM_ENGINE_IDENTIFIERS["MiniMax"],
            MinimaxTranslation,
        )

    def test_get_engine_class_for_minimax_m27(self):
        cls = self.Factory._get_engine_class("MiniMax-M2.7")
        self.assertIs(cls, MinimaxTranslation)

    def test_get_engine_class_for_minimax_highspeed(self):
        cls = self.Factory._get_engine_class("MiniMax-M2.7-highspeed")
        self.assertIs(cls, MinimaxTranslation)


class TestMinimaxPerformTranslation(unittest.TestCase):
    """Test _perform_translation builds correct API payloads."""

    def _make_engine(self):
        engine = MinimaxTranslation()
        engine.api_key = "test-key"
        engine.model = "MiniMax-M2.7"
        engine.temperature = 1.0
        engine.top_p = 0.95
        engine.max_tokens = 5000
        engine.img_as_llm_input = False
        return engine

    @patch("modules.translation.llm.gpt.requests.post")
    def test_text_only_payload(self, mock_post):
        engine = self._make_engine()

        mock_response = MagicMock()
        mock_response.json.return_value = {
            "choices": [{"message": {"content": '{"block_0": "translated"}'}}]
        }
        mock_response.raise_for_status = MagicMock()
        mock_post.return_value = mock_response

        result = engine._perform_translation(
            "translate this", "you are a translator",
            np.zeros((10, 10, 3), dtype=np.uint8),
        )

        self.assertEqual(result, '{"block_0": "translated"}')
        call_url = mock_post.call_args[0][0]
        self.assertEqual(call_url, "https://api.minimax.io/v1/chat/completions")

    @patch("modules.translation.llm.gpt.requests.post")
    def test_api_url_uses_minimax(self, mock_post):
        engine = self._make_engine()

        mock_response = MagicMock()
        mock_response.json.return_value = {
            "choices": [{"message": {"content": "{}"}}]
        }
        mock_response.raise_for_status = MagicMock()
        mock_post.return_value = mock_response

        engine._perform_translation("test", "system", np.zeros((5, 5, 3), dtype=np.uint8))

        url = mock_post.call_args[0][0]
        self.assertTrue(url.startswith("https://api.minimax.io/v1"))

    @patch("modules.translation.llm.gpt.requests.post")
    def test_auth_header(self, mock_post):
        engine = self._make_engine()

        mock_response = MagicMock()
        mock_response.json.return_value = {
            "choices": [{"message": {"content": "{}"}}]
        }
        mock_response.raise_for_status = MagicMock()
        mock_post.return_value = mock_response

        engine._perform_translation("test", "system", np.zeros((5, 5, 3), dtype=np.uint8))

        headers = mock_post.call_args.kwargs.get("headers")
        if headers is None:
            headers = mock_post.call_args[1].get("headers")
        self.assertEqual(headers["Authorization"], "Bearer test-key")

    @patch("modules.translation.llm.gpt.requests.post")
    def test_payload_model_field(self, mock_post):
        engine = self._make_engine()

        mock_response = MagicMock()
        mock_response.json.return_value = {
            "choices": [{"message": {"content": "{}"}}]
        }
        mock_response.raise_for_status = MagicMock()
        mock_post.return_value = mock_response

        engine._perform_translation("test", "system", np.zeros((5, 5, 3), dtype=np.uint8))

        data = mock_post.call_args.kwargs.get("data") or mock_post.call_args[1].get("data")
        payload = json.loads(data)
        self.assertEqual(payload["model"], "MiniMax-M2.7")

    @patch("modules.translation.llm.gpt.requests.post")
    def test_payload_temperature(self, mock_post):
        engine = self._make_engine()

        mock_response = MagicMock()
        mock_response.json.return_value = {
            "choices": [{"message": {"content": "{}"}}]
        }
        mock_response.raise_for_status = MagicMock()
        mock_post.return_value = mock_response

        engine._perform_translation("test", "system", np.zeros((5, 5, 3), dtype=np.uint8))

        data = mock_post.call_args.kwargs.get("data") or mock_post.call_args[1].get("data")
        payload = json.loads(data)
        self.assertEqual(payload["temperature"], 1.0)
        self.assertEqual(payload["top_p"], 0.95)


class TestMinimaxErrorHandling(unittest.TestCase):
    """Test error handling in MiniMax translation."""

    def _make_engine(self):
        engine = MinimaxTranslation()
        engine.api_key = "test-key"
        engine.model = "MiniMax-M2.7"
        engine.temperature = 1.0
        engine.top_p = 0.95
        engine.max_tokens = 5000
        engine.img_as_llm_input = False
        return engine

    @patch("modules.translation.llm.gpt.requests.post")
    def test_api_error_raises_runtime_error(self, mock_post):
        import requests as req
        engine = self._make_engine()

        mock_response = MagicMock()
        mock_response.status_code = 401
        mock_response.json.return_value = {"error": {"message": "Invalid API key"}}
        mock_post.side_effect = req.exceptions.HTTPError(response=mock_response)

        with self.assertRaises(RuntimeError) as ctx:
            engine._perform_translation("test", "system", np.zeros((5, 5, 3), dtype=np.uint8))
        self.assertIn("API request failed", str(ctx.exception))

    @patch("modules.translation.llm.gpt.requests.post")
    def test_timeout_raises_runtime_error(self, mock_post):
        import requests as req
        engine = self._make_engine()
        mock_post.side_effect = req.exceptions.Timeout("Connection timed out")

        with self.assertRaises(RuntimeError) as ctx:
            engine._perform_translation("test", "system", np.zeros((5, 5, 3), dtype=np.uint8))
        self.assertIn("API request failed", str(ctx.exception))

    @patch("modules.translation.llm.gpt.requests.post")
    def test_connection_error_raises_runtime_error(self, mock_post):
        import requests as req
        engine = self._make_engine()
        mock_post.side_effect = req.exceptions.ConnectionError("DNS resolution failed")

        with self.assertRaises(RuntimeError) as ctx:
            engine._perform_translation("test", "system", np.zeros((5, 5, 3), dtype=np.uint8))
        self.assertIn("API request failed", str(ctx.exception))


# ---------------------------------------------------------------------------
# Integration Tests – require MINIMAX_API_KEY env var
# ---------------------------------------------------------------------------

class TestMinimaxIntegration(unittest.TestCase):
    """Integration tests that call the real MiniMax API.

    These tests are skipped unless MINIMAX_API_KEY is set in the environment.
    """

    @classmethod
    def setUpClass(cls):
        cls.api_key = os.environ.get("MINIMAX_API_KEY", "")
        if not cls.api_key:
            raise unittest.SkipTest("MINIMAX_API_KEY not set; skipping integration tests")

    def _make_engine(self, model="MiniMax-M2.7"):
        engine = MinimaxTranslation()
        engine.api_key = self.api_key
        engine.model = model
        engine.source_lang = "Japanese"
        engine.target_lang = "English"
        engine.temperature = 1.0
        engine.top_p = 0.95
        engine.max_tokens = 5000
        engine.img_as_llm_input = False
        engine.timeout = 60
        return engine

    def test_real_translation_m27(self):
        engine = self._make_engine("MiniMax-M2.7")
        result = engine._perform_translation(
            'Translate this:\n{"block_0": "こんにちは"}',
            "You are a professional translator. Translate from Japanese to English. Output as JSON.",
            np.zeros((10, 10, 3), dtype=np.uint8),
        )
        self.assertIn("block_0", result)

    def test_real_translation_m27_highspeed(self):
        engine = self._make_engine("MiniMax-M2.7-highspeed")
        result = engine._perform_translation(
            'Translate this:\n{"block_0": "ありがとう"}',
            "You are a professional translator. Translate from Japanese to English. Output as JSON.",
            np.zeros((10, 10, 3), dtype=np.uint8),
        )
        self.assertIn("block_0", result)

    def test_real_api_returns_valid_json(self):
        import re as re_mod
        engine = self._make_engine("MiniMax-M2.7")
        result = engine._perform_translation(
            'Translate this:\n{"block_0": "猫"}',
            "You are a professional translator. Translate from Japanese to English. Return valid JSON only.",
            np.zeros((10, 10, 3), dtype=np.uint8),
        )
        match = re_mod.search(r"\{[\s\S]*\}", result)
        self.assertIsNotNone(match, "Response should contain JSON")
        parsed = json.loads(match.group(0))
        self.assertIn("block_0", parsed)


if __name__ == "__main__":
    unittest.main()
