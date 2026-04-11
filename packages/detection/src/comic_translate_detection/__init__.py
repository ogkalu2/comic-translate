"""
Comic Translate Detection Package

Panel and bubble detection for comic images.
"""

from .detector import DetectionEngine, PanelDetector, BubbleDetector

__all__ = [
    "DetectionEngine",
    "PanelDetector",
    "BubbleDetector",
]
