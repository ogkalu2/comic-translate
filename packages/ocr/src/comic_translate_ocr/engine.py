"""
OCR engine wrappers for text extraction from comic images.
"""

from abc import ABC, abstractmethod
from typing import List, Optional, Tuple
import numpy as np


class OCREngine(ABC):
    """
    Abstract base class for OCR engines.
    Wraps the core OCR interface.
    """

    @abstractmethod
    def initialize(self, **kwargs) -> None:
        """Initialize the OCR engine."""
        pass

    @abstractmethod
    def process_image(self, img: np.ndarray, blk_list: list) -> list:
        """
        Process an image with OCR and update text blocks.

        Args:
            img: Input image as numpy array
            blk_list: List of text blocks to update

        Returns:
            List of updated text blocks with recognized text
        """
        pass


class OCREngineFactory:
    """Factory for creating OCR engines."""

    _engines = {
        "manga_ocr": "modules.ocr.manga_ocr.engine.MangaOCREngine",
        "pororo": "modules.ocr.pororo.engine.PororoEngine",
        "google": "modules.ocr.google_ocr.GoogleOCREngine",
        "microsoft": "modules.ocr.microsoft_ocr.MicrosoftOCREngine",
        "gpt": "modules.ocr.gpt_ocr.GPTOCREngine",
        "gemini": "modules.ocr.gemini_ocr.GeminiOCREngine",
        "user": "modules.ocr.user_ocr.UserOCREngine",
    }

    @classmethod
    def create_engine(
        cls,
        engine_type: str = "manga_ocr",
        **kwargs
    ) -> OCREngine:
        """
        Create an OCR engine instance.

        Args:
            engine_type: Type of OCR engine to create
            **kwargs: Engine-specific parameters

        Returns:
            OCR engine instance
        """
        if engine_type not in cls._engines:
            raise ValueError(f"Unknown OCR engine type: {engine_type}")

        # Dynamic import to avoid circular dependencies
        module_path, class_name = cls._engines[engine_type].rsplit(".", 1)
        import importlib
        module = importlib.import_module(module_path)
        engine_class = getattr(module, class_name)

        return engine_class(**kwargs)

    @classmethod
    def get_available_engines(cls) -> List[str]:
        """Get list of available OCR engine types."""
        return list(cls._engines.keys())
