"""
OCR engine interface for text extraction from comic images.
"""

from abc import ABC, abstractmethod
from typing import List, Optional, Tuple


class IOCREngine(ABC):
    """
    Interface for Optical Character Recognition (OCR) engines.
    
    Extracts text from comic bubble regions with position and confidence information.
    """

    @abstractmethod
    def recognize(self, image_path: str, bbox: List[int]) -> str:
        """
        Recognize text in a specific region of an image.

        Args:
            image_path: Path to the comic page image
            bbox: Bounding box [x1, y1, x2, y2] defining the region

        Returns:
            Recognized text string
        """
        ...

    @abstractmethod
    def recognize_with_confidence(
        self, image_path: str, bbox: List[int]
    ) -> Tuple[str, float]:
        """
        Recognize text with confidence score.

        Args:
            image_path: Path to the comic page image
            bbox: Bounding box [x1, y1, x2, y2] defining the region

        Returns:
            Tuple of (recognized_text, confidence_score)
        """
        ...

    @abstractmethod
    def recognize_batch(
        self, image_path: str, bboxes: List[List[int]]
    ) -> List[Tuple[str, float]]:
        """
        Recognize text in multiple regions of an image.

        Args:
            image_path: Path to the comic page image
            bboxes: List of bounding boxes, each as [x1, y1, x2, y2]

        Returns:
            List of tuples containing (recognized_text, confidence_score)
        """
        ...

    @abstractmethod
    def get_supported_languages(self) -> List[str]:
        """
        Get list of supported language codes.

        Returns:
            List of ISO 639-1 language codes (e.g., ["en", "ja", "ko"])
        """
        ...

    @abstractmethod
    def set_language(self, language: str) -> None:
        """
        Set the primary language for OCR recognition.

        Args:
            language: ISO 639-1 language code

        Raises:
            ValueError: If language is not supported
        """
        ...
