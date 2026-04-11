"""
Adapters for wrapping external package implementations.

These adapters provide a unified interface for the core package
to interact with detection, OCR, translation, and rendering packages.
"""

from .detection import DetectionAdapter
from .ocr import OCRAdapter
from .translation import TranslationAdapter
from .rendering import RenderingAdapter, InpaintingAdapter

__all__ = [
    "DetectionAdapter",
    "OCRAdapter",
    "TranslationAdapter",
    "RenderingAdapter",
    "InpaintingAdapter",
]
