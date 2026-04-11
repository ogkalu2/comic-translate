"""
Comic Translate Translation Package

Translation providers for comic text translation.
"""

from .engine import TranslationEngine, TranslationEngineFactory

__all__ = [
    "TranslationEngine",
    "TranslationEngineFactory",
]
