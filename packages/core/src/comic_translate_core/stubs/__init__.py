"""
Stub implementations for testing the pipeline without external dependencies.
"""

from .detector import StubPanelDetector, StubBubbleDetector
from .ocr import StubOCREngine
from .translator import StubTranslator
from .inpainter import StubInpainter
from .renderer import StubRenderer

__all__ = [
    "StubPanelDetector",
    "StubBubbleDetector",
    "StubOCREngine",
    "StubTranslator",
    "StubInpainter",
    "StubRenderer",
]
