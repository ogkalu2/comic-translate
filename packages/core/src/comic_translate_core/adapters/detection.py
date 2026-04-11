"""
Detection adapter for wrapping detection package implementations.
"""

from typing import Any, List, Optional
import numpy as np

from ..interfaces.detector import IPanelDetector, IBubbleDetector


class DetectionAdapter:
    """
    Adapter for detection engines.
    Wraps the detection package to implement core interfaces.
    """

    def __init__(self, engine_type: str = "rtdetr", **kwargs):
        self.engine_type = engine_type
        self._engine = None
        self._kwargs = kwargs

    def _get_engine(self):
        """Lazy load the detection engine."""
        if self._engine is None:
            from comic_translate_detection.detector import DetectionEngineFactory
            self._engine = DetectionEngineFactory.create_engine(
                engine_type=self.engine_type,
                **self._kwargs
            )
        return self._engine

    def detect_panels(self, image: np.ndarray) -> List[List[int]]:
        """
        Detect panels in an image.

        Args:
            image: Input image as numpy array

        Returns:
            List of bounding boxes [x1, y1, x2, y2]
        """
        engine = self._get_engine()
        return engine.detect(image, detection_type="panel")

    def detect_bubbles(self, image: np.ndarray) -> List[List[int]]:
        """
        Detect bubbles in an image.

        Args:
            image: Input image as numpy array

        Returns:
            List of bounding boxes [x1, y1, x2, y2]
        """
        engine = self._get_engine()
        return engine.detect(image, detection_type="bubble")


class PanelDetectorAdapter(IPanelDetector):
    """Adapter implementing IPanelDetector interface."""

    def __init__(self, engine_type: str = "rtdetr", **kwargs):
        self._adapter = DetectionAdapter(engine_type=engine_type, **kwargs)

    def detect(self, image_path: str) -> List[List[int]]:
        """Detect panels from image path."""
        import cv2
        image = cv2.imread(image_path)
        return self._adapter.detect_panels(image)

    def detect_from_image(self, image_data: bytes) -> List[List[int]]:
        """Detect panels from image bytes."""
        import cv2
        import numpy as np
        nparr = np.frombuffer(image_data, np.uint8)
        image = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
        return self._adapter.detect_panels(image)


class BubbleDetectorAdapter(IBubbleDetector):
    """Adapter implementing IBubbleDetector interface."""

    def __init__(self, engine_type: str = "rtdetr", **kwargs):
        self._adapter = DetectionAdapter(engine_type=engine_type, **kwargs)

    def detect(self, image_path: str) -> List[List[int]]:
        """Detect bubbles from image path."""
        import cv2
        image = cv2.imread(image_path)
        return self._adapter.detect_bubbles(image)

    def detect_from_image(self, image_data: bytes) -> List[List[int]]:
        """Detect bubbles from image bytes."""
        import cv2
        import numpy as np
        nparr = np.frombuffer(image_data, np.uint8)
        image = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
        return self._adapter.detect_bubbles(image)
