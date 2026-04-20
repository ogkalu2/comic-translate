from __future__ import annotations

from abc import ABC, abstractmethod
import numpy as np
from typing import TYPE_CHECKING, Optional

from .text_block_builder import create_text_blocks

if TYPE_CHECKING:
    from ..utils.textblock import TextBlock


class DetectionEngine(ABC):
    """
    Abstract base class for all detection engines.
    Each model implementation should inherit from this class.
    """
    
    def __init__(self, settings=None):
        self.settings = settings
    
    @abstractmethod
    def initialize(self, **kwargs) -> None:
        """
        Initialize the detection model with necessary parameters.
        
        Args:
            **kwargs: Engine-specific initialization parameters
        """
        pass
    
    @abstractmethod
    def detect(self, image: np.ndarray) -> list[TextBlock]:
        """
        Detect text blocks in an image.
        
        Args:
            image: Input image as numpy array
            
        Returns:
            List of TextBlock objects with detected regions
        """
        pass

    def supports_image_batching(self) -> bool:
        return False

    def detect_many(self, images: list[np.ndarray]) -> list[list[TextBlock]]:
        return [self.detect(image) for image in images]
        
    def create_text_blocks(
        self, 
        image: np.ndarray, 
        text_boxes: np.ndarray,
        bubble_boxes: Optional[np.ndarray] = None
    ) -> list[TextBlock]:
        return create_text_blocks(self.settings, image, text_boxes, bubble_boxes)
    
