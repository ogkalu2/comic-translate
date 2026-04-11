"""
Stub OCR engine implementation for testing.
"""

from typing import Dict, List, Optional, Tuple

from ..interfaces import IOCREngine


class StubOCREngine(IOCREngine):
    """
    Stub OCR engine that returns predefined text.
    
    Useful for testing the pipeline without actual OCR models.
    """

    def __init__(
        self,
        text_map: Optional[Dict[Tuple[int, ...], Tuple[str, float]]] = None,
        default_text: str = "Sample text",
        default_confidence: float = 0.95,
    ):
        """
        Initialize with optional text mapping.

        Args:
            text_map: Dictionary mapping bbox tuples to (text, confidence)
            default_text: Default text to return for unmapped regions
            default_confidence: Default confidence score
        """
        self.text_map = text_map or {}
        self.default_text = default_text
        self.default_confidence = default_confidence
        self._language = "en"

    def recognize(self, image_path: str, bbox: List[int]) -> str:
        """
        Return predefined text for a region.

        Args:
            image_path: Path to the comic page image (ignored)
            bbox: Bounding box [x1, y1, x2, y2]

        Returns:
            Recognized text string
        """
        bbox_tuple = tuple(bbox)
        if bbox_tuple in self.text_map:
            return self.text_map[bbox_tuple][0]
        return self.default_text

    def recognize_with_confidence(
        self, image_path: str, bbox: List[int]
    ) -> Tuple[str, float]:
        """
        Return predefined text with confidence for a region.

        Args:
            image_path: Path to the comic page image (ignored)
            bbox: Bounding box [x1, y1, x2, y2]

        Returns:
            Tuple of (recognized_text, confidence_score)
        """
        bbox_tuple = tuple(bbox)
        if bbox_tuple in self.text_map:
            return self.text_map[bbox_tuple]
        return (self.default_text, self.default_confidence)

    def recognize_batch(
        self, image_path: str, bboxes: List[List[int]]
    ) -> List[Tuple[str, float]]:
        """
        Return predefined text with confidence for multiple regions.

        Args:
            image_path: Path to the comic page image (ignored)
            bboxes: List of bounding boxes, each as [x1, y1, x2, y2]

        Returns:
            List of tuples containing (recognized_text, confidence_score)
        """
        return [self.recognize_with_confidence(image_path, bbox) for bbox in bboxes]

    def get_supported_languages(self) -> List[str]:
        """
        Get list of supported language codes.

        Returns:
            List of ISO 639-1 language codes
        """
        return ["en", "ja", "ko", "zh"]

    def set_language(self, language: str) -> None:
        """
        Set the primary language for OCR recognition.

        Args:
            language: ISO 639-1 language code

        Raises:
            ValueError: If language is not supported
        """
        supported = self.get_supported_languages()
        if language not in supported:
            raise ValueError(f"Language '{language}' not supported. Supported: {supported}")
        self._language = language
