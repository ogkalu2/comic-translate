"""
OCR adapter for wrapping OCR package implementations.
"""

from typing import Any, List, Optional, Tuple
import numpy as np

from ..interfaces.ocr import IOCREngine


class OCRAdapter:
    """
    Adapter for OCR engines.
    Wraps the OCR package to implement core interfaces.
    """

    def __init__(self, engine_type: str = "manga_ocr", **kwargs):
        self.engine_type = engine_type
        self._engine = None
        self._kwargs = kwargs

    def _get_engine(self):
        """Lazy load the OCR engine."""
        if self._engine is None:
            from comic_translate_ocr.engine import OCREngineFactory
            self._engine = OCREngineFactory.create_engine(
                engine_type=self.engine_type,
                **self._kwargs
            )
        return self._engine

    def process_image(self, img: np.ndarray, blk_list: list) -> list:
        """
        Process an image with OCR.

        Args:
            img: Input image as numpy array
            blk_list: List of text blocks to update

        Returns:
            List of updated text blocks with recognized text
        """
        engine = self._get_engine()
        return engine.process_image(img, blk_list)


class OCREngineAdapter(IOCREngine):
    """Adapter implementing IOCREngine interface."""

    def __init__(self, engine_type: str = "manga_ocr", **kwargs):
        self._adapter = OCRAdapter(engine_type=engine_type, **kwargs)

    def recognize(self, image_path: str, bbox: List[int]) -> str:
        """Recognize text in a specific region."""
        import cv2
        image = cv2.imread(image_path)
        x1, y1, x2, y2 = bbox
        crop = image[y1:y2, x1:x2]

        # Create a temporary text block for OCR
        from modules.utils.textblock import TextBlock
        blk = TextBlock()
        blk.xyxy = bbox

        result = self._adapter.process_image(crop, [blk])
        if result:
            return result[0].text or ""
        return ""

    def recognize_with_confidence(
        self, image_path: str, bbox: List[int]
    ) -> Tuple[str, float]:
        """Recognize text with confidence score."""
        text = self.recognize(image_path, bbox)
        # Default confidence since not all engines provide it
        return text, 1.0 if text else 0.0

    def recognize_batch(
        self, image_path: str, bboxes: List[List[int]]
    ) -> List[Tuple[str, float]]:
        """Recognize text in multiple regions."""
        results = []
        for bbox in bboxes:
            text, confidence = self.recognize_with_confidence(image_path, bbox)
            results.append((text, confidence))
        return results
