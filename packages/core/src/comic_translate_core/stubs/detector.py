"""
Stub implementations of panel and bubble detectors for testing.
"""

from typing import List, Optional, Tuple

from ..interfaces import IPanelDetector, IBubbleDetector


class StubPanelDetector(IPanelDetector):
    """
    Stub panel detector that returns predefined panel regions.
    
    Useful for testing the pipeline without actual detection models.
    """

    def __init__(self, panels: Optional[List[List[int]]] = None):
        """
        Initialize with optional predefined panels.

        Args:
            panels: List of panel bounding boxes, each as [x1, y1, x2, y2]
        """
        self.panels = panels or [[0, 0, 500, 750]]

    def detect(self, image_path: str) -> List[List[int]]:
        """
        Return predefined panels.

        Args:
            image_path: Path to the comic page image (ignored)

        Returns:
            List of panel bounding boxes
        """
        return self.panels.copy()

    def detect_from_image(self, image_data: bytes) -> List[List[int]]:
        """
        Return predefined panels.

        Args:
            image_data: Raw image bytes (ignored)

        Returns:
            List of panel bounding boxes
        """
        return self.panels.copy()


class StubBubbleDetector(IBubbleDetector):
    """
    Stub bubble detector that returns predefined bubble regions.
    
    Useful for testing the pipeline without actual detection models.
    """

    def __init__(self, bubbles: Optional[List[Tuple[List[int], str]]] = None):
        """
        Initialize with optional predefined bubbles.

        Args:
            bubbles: List of (bbox, bubble_type) tuples
        """
        self.bubbles = bubbles or [
            ([50, 50, 200, 150], "speech"),
            ([250, 200, 400, 300], "speech"),
        ]

    def detect(self, image_path: str) -> List[Tuple[List[int], str]]:
        """
        Return predefined bubbles.

        Args:
            image_path: Path to the comic page image (ignored)

        Returns:
            List of (bbox, bubble_type) tuples
        """
        return self.bubbles.copy()

    def detect_from_image(self, image_data: bytes) -> List[Tuple[List[int], str]]:
        """
        Return predefined bubbles.

        Args:
            image_data: Raw image bytes (ignored)

        Returns:
            List of (bbox, bubble_type) tuples
        """
        return self.bubbles.copy()

    def classify_bubble(self, bbox: List[int], image_path: str) -> str:
        """
        Return the bubble type for a given bbox if it matches a predefined bubble.

        Args:
            bbox: Bounding box [x1, y1, x2, y2]
            image_path: Path to the comic page image (ignored)

        Returns:
            Bubble type string
        """
        for bubble_bbox, bubble_type in self.bubbles:
            if bubble_bbox == bbox:
                return bubble_type
        return "speech"
