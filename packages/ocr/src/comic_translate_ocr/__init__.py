"""
Comic Translate OCR Package

OCR engines for text extraction from comic images.
"""

from .engine import OCREngine, OCREngineFactory

__all__ = [
    "OCREngine",
    "OCREngineFactory",
]
