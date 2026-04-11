"""
Detector interfaces for panel and bubble detection in comic images.
"""

from abc import ABC, abstractmethod
from typing import List, Tuple


class IPanelDetector(ABC):
    """
    Interface for detecting panels in comic page images.
    
    Panels are the rectangular regions that contain comic content.
    """

    @abstractmethod
    def detect(self, image_path: str) -> List[List[int]]:
        """
        Detect panels in a comic page image.

        Args:
            image_path: Path to the comic page image

        Returns:
            List of bounding boxes, each as [x1, y1, x2, y2]
        """
        ...

    @abstractmethod
    def detect_from_image(self, image_data: bytes) -> List[List[int]]:
        """
        Detect panels from raw image data.

        Args:
            image_data: Raw image bytes

        Returns:
            List of bounding boxes, each as [x1, y1, x2, y2]
        """
        ...


class IBubbleDetector(ABC):
    """
    Interface for detecting speech bubbles in comic page images.
    
    Speech bubbles contain dialogue text that needs to be extracted and translated.
    """

    @abstractmethod
    def detect(self, image_path: str) -> List[Tuple[List[int], str]]:
        """
        Detect speech bubbles in a comic page image.

        Args:
            image_path: Path to the comic page image

        Returns:
            List of tuples containing (bbox, bubble_type) where:
            - bbox is [x1, y1, x2, y2]
            - bubble_type is one of: "speech", "thought", "narration", "sfx"
        """
        ...

    @abstractmethod
    def detect_from_image(self, image_data: bytes) -> List[Tuple[List[int], str]]:
        """
        Detect speech bubbles from raw image data.

        Args:
            image_data: Raw image bytes

        Returns:
            List of tuples containing (bbox, bubble_type)
        """
        ...

    @abstractmethod
    def classify_bubble(self, bbox: List[int], image_path: str) -> str:
        """
        Classify the type of a detected bubble region.

        Args:
            bbox: Bounding box [x1, y1, x2, y2]
            image_path: Path to the comic page image

        Returns:
            Bubble type: "speech", "thought", "narration", or "sfx"
        """
        ...
