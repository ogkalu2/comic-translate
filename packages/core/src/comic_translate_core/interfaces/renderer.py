"""
Renderer interface for rendering translated text onto comic images.
"""

from abc import ABC, abstractmethod
from typing import List, Optional, Tuple

import numpy as np


class IRenderer(ABC):
    """
    Interface for rendering translated text onto comic images.
    
    Handles font selection, text layout, and positioning within bubble regions.
    """

    @abstractmethod
    def render(
        self,
        image: np.ndarray,
        text: str,
        bbox: List[int],
        font_size: Optional[int] = None,
        font_color: Optional[Tuple[int, int, int]] = None,
    ) -> np.ndarray:
        """
        Render translated text onto an image within a bounding box.

        Args:
            image: Input image as numpy array
            text: Text to render
            bbox: Bounding box [x1, y1, x2, y2] for text placement
            font_size: Optional font size (auto-calculated if None)
            font_color: Optional RGB font color (default: black)

        Returns:
            Image with rendered text as numpy array
        """
        ...

    @abstractmethod
    def render_batch(
        self,
        image: np.ndarray,
        texts: List[str],
        bboxes: List[List[int]],
        font_sizes: Optional[List[int]] = None,
        font_colors: Optional[List[Tuple[int, int, int]]] = None,
    ) -> np.ndarray:
        """
        Render multiple texts onto an image.

        Args:
            image: Input image as numpy array
            texts: List of texts to render
            bboxes: List of bounding boxes for text placement
            font_sizes: Optional list of font sizes
            font_colors: Optional list of RGB font colors

        Returns:
            Image with all rendered texts as numpy array
        """
        ...

    @abstractmethod
    def calculate_font_size(
        self,
        text: str,
        bbox: List[int],
        max_font_size: int = 48,
        min_font_size: int = 12,
    ) -> int:
        """
        Calculate optimal font size for text within a bounding box.

        Args:
            text: Text to fit
            bbox: Bounding box [x1, y1, x2, y2]
            max_font_size: Maximum allowed font size
            min_font_size: Minimum allowed font size

        Returns:
            Calculated font size
        """
        ...

    @abstractmethod
    def get_available_fonts(self) -> List[str]:
        """
        Get list of available font names.

        Returns:
            List of font names
        """
        ...

    @abstractmethod
    def set_font(self, font_name: str) -> None:
        """
        Set the font for rendering.

        Args:
            font_name: Name of the font to use

        Raises:
            ValueError: If font is not available
        """
        ...
