"""
Stub renderer implementation for testing.
"""

from typing import List, Optional, Tuple

import numpy as np

from ..interfaces import IRenderer


class StubRenderer(IRenderer):
    """
    Stub renderer that draws simple text placeholders.
    
    Useful for testing the pipeline without actual rendering models.
    """

    def __init__(
        self,
        default_font_size: int = 24,
        default_font_color: Tuple[int, int, int] = (0, 0, 0),
    ):
        """
        Initialize with optional default settings.

        Args:
            default_font_size: Default font size for rendering
            default_font_color: Default RGB font color (default: black)
        """
        self.default_font_size = default_font_size
        self.default_font_color = default_font_color
        self._font_name = "default"

    def render(
        self,
        image: np.ndarray,
        text: str,
        bbox: List[int],
        font_size: Optional[int] = None,
        font_color: Optional[Tuple[int, int, int]] = None,
    ) -> np.ndarray:
        """
        Render a simple text placeholder on the image.

        Args:
            image: Input image as numpy array
            text: Text to render
            bbox: Bounding box [x1, y1, x2, y2] for text placement
            font_size: Optional font size (ignored)
            font_color: Optional RGB font color (ignored)

        Returns:
            Image with rendered text placeholder as numpy array
        """
        result = image.copy()
        x1, y1, x2, y2 = bbox
        
        # Draw a simple rectangle to indicate where text would be rendered
        color = font_color or self.default_font_color
        result[y1:y1+2, x1:x2] = color  # Top border
        result[y2-2:y2, x1:x2] = color  # Bottom border
        result[y1:y2, x1:x1+2] = color  # Left border
        result[y1:y2, x2-2:x2] = color  # Right border
        
        return result

    def render_batch(
        self,
        image: np.ndarray,
        texts: List[str],
        bboxes: List[List[int]],
        font_sizes: Optional[List[int]] = None,
        font_colors: Optional[List[Tuple[int, int, int]]] = None,
    ) -> np.ndarray:
        """
        Render multiple text placeholders onto an image.

        Args:
            image: Input image as numpy array
            texts: List of texts to render
            bboxes: List of bounding boxes for text placement
            font_sizes: Optional list of font sizes (ignored)
            font_colors: Optional list of RGB font colors (ignored)

        Returns:
            Image with all rendered text placeholders as numpy array
        """
        result = image.copy()
        
        for i, (text, bbox) in enumerate(zip(texts, bboxes)):
            font_size = None
            if font_sizes and i < len(font_sizes):
                font_size = font_sizes[i]
            
            font_color = None
            if font_colors and i < len(font_colors):
                font_color = font_colors[i]
            
            result = self.render(result, text, bbox, font_size, font_color)
        
        return result

    def calculate_font_size(
        self,
        text: str,
        bbox: List[int],
        max_font_size: int = 48,
        min_font_size: int = 12,
    ) -> int:
        """
        Calculate a simple font size based on bbox dimensions.

        Args:
            text: Text to fit
            bbox: Bounding box [x1, y1, x2, y2]
            max_font_size: Maximum allowed font size
            min_font_size: Minimum allowed font size

        Returns:
            Calculated font size
        """
        x1, y1, x2, y2 = bbox
        height = y2 - y1
        
        # Simple heuristic: font size proportional to height
        font_size = int(height * 0.5)
        
        return max(min_font_size, min(max_font_size, font_size))

    def get_available_fonts(self) -> List[str]:
        """
        Get list of available font names.

        Returns:
            List of font names
        """
        return ["default", "stub_font"]

    def set_font(self, font_name: str) -> None:
        """
        Set the font for rendering.

        Args:
            font_name: Name of the font to use

        Raises:
            ValueError: If font is not available
        """
        available = self.get_available_fonts()
        if font_name not in available:
            raise ValueError(f"Font '{font_name}' not available. Available: {available}")
        self._font_name = font_name
