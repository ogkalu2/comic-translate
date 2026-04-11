"""
Translation engine wrappers for comic text translation.
"""

from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional
import numpy as np


class TranslationEngine(ABC):
    """
    Abstract base class for translation engines.
    Wraps the core translation interface.
    """

    @abstractmethod
    def initialize(self, settings: Any, source_lang: str, target_lang: str, **kwargs) -> None:
        """Initialize the translation engine."""
        pass

    @abstractmethod
    def translate(self, blk_list: list, **kwargs) -> list:
        """
        Translate text blocks.

        Args:
            blk_list: List of text blocks to translate
            **kwargs: Additional translation parameters

        Returns:
            List of translated text blocks
        """
        pass


class TranslationEngineFactory:
    """Factory for creating translation engines."""

    _engines = {
        "deepl": "modules.translation.deepl.DeepLEngine",
        "microsoft": "modules.translation.microsoft.MicrosoftEngine",
        "yandex": "modules.translation.yandex.YandexEngine",
        "user": "modules.translation.user.UserEngine",
        "gpt": "modules.translation.llm.gpt.GPTEngine",
        "claude": "modules.translation.llm.claude.ClaudeEngine",
        "gemini": "modules.translation.llm.gemini.GeminiEngine",
        "deepseek": "modules.translation.llm.deepseek.DeepSeekEngine",
        "openrouter": "modules.translation.llm.openrouter.OpenRouterEngine",
        "github": "modules.translation.llm.github.GitHubEngine",
        "xai": "modules.translation.llm.xai.XAIEngine",
        "custom": "modules.translation.llm.custom.CustomEngine",
    }

    @classmethod
    def create_engine(
        cls,
        engine_type: str = "gpt",
        **kwargs
    ) -> TranslationEngine:
        """
        Create a translation engine instance.

        Args:
            engine_type: Type of translation engine to create
            **kwargs: Engine-specific parameters

        Returns:
            Translation engine instance
        """
        if engine_type not in cls._engines:
            raise ValueError(f"Unknown translation engine type: {engine_type}")

        # Dynamic import to avoid circular dependencies
        module_path, class_name = cls._engines[engine_type].rsplit(".", 1)
        import importlib
        module = importlib.import_module(module_path)
        engine_class = getattr(module, class_name)

        return engine_class(**kwargs)

    @classmethod
    def get_available_engines(cls) -> List[str]:
        """Get list of available translation engine types."""
        return list(cls._engines.keys())
