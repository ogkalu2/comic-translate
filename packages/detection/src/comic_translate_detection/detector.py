"""
Detection engine wrappers for panel and bubble detection.
"""

from abc import ABC, abstractmethod
from typing import List, Optional, Tuple
import numpy as np


class DetectionEngine(ABC):
    """
    Abstract base class for detection engines.
    Wraps the core detection interface.
    """

    @abstractmethod
    def initialize(self, **kwargs) -> None:
        """Initialize the detection engine."""
        pass

    @abstractmethod
    def detect(self, image: np.ndarray) -> list:
        """
        Detect text blocks in an image.

        Args:
            image: Input image as numpy array

        Returns:
            List of detected text blocks
        """
        pass


class PanelDetector(DetectionEngine):
    """
    Panel detector for comic page images.
    Detects rectangular panel regions.
    """

    def __init__(self, backend: str = "rtdetr"):
        self.backend = backend
        self._engine = None

    def initialize(self, **kwargs) -> None:
        """Initialize the panel detection engine."""
        # Import here to avoid circular dependencies
        from modules.detection.factory import DetectionEngineFactory
        self._engine = DetectionEngineFactory.create_engine(
            settings=kwargs.get("settings"),
            model_name=kwargs.get("model_name", "RT-DETR-v2"),
            backend=self.backend
        )

    def detect(self, image: np.ndarray) -> list:
        """Detect panels in the image."""
        if self._engine is None:
            raise RuntimeError("Engine not initialized. Call initialize() first.")
        return self._engine.detect(image)


class BubbleDetector(DetectionEngine):
    """
    Bubble detector for comic page images.
    Detects speech bubble regions.
    """

    def __init__(self, backend: str = "rtdetr"):
        self.backend = backend
        self._engine = None

    def initialize(self, **kwargs) -> None:
        """Initialize the bubble detection engine."""
        from modules.detection.factory import DetectionEngineFactory
        self._engine = DetectionEngineFactory.create_engine(
            settings=kwargs.get("settings"),
            model_name=kwargs.get("model_name", "RT-DETR-v2"),
            backend=self.backend
        )

    def detect(self, image: np.ndarray) -> list:
        """Detect bubbles in the image."""
        if self._engine is None:
            raise RuntimeError("Engine not initialized. Call initialize() first.")
        return self._engine.detect(image)
