"""
Inpainter interface for removing text from comic images.
"""

from abc import ABC, abstractmethod
from typing import List, Optional, Tuple

import numpy as np


class IInpainter(ABC):
    """
    Interface for inpainting (text removal) from comic images.
    
    Removes original text from bubble regions to prepare for translation rendering.
    """

    @abstractmethod
    def inpaint(
        self,
        image_path: str,
        bbox: List[int],
        mask: Optional[np.ndarray] = None,
    ) -> np.ndarray:
        """
        Inpaint (remove text) from a specific region of an image.

        Args:
            image_path: Path to the comic page image
            bbox: Bounding box [x1, y1, x2, y2] defining the region
            mask: Optional binary mask indicating text pixels to remove

        Returns:
            Inpainted image as numpy array
        """
        ...

    @abstractmethod
    def inpaint_batch(
        self,
        image_path: str,
        bboxes: List[List[int]],
        masks: Optional[List[np.ndarray]] = None,
    ) -> np.ndarray:
        """
        Inpaint multiple regions of an image.

        Args:
            image_path: Path to the comic page image
            bboxes: List of bounding boxes, each as [x1, y1, x2, y2]
            masks: Optional list of binary masks for each region

        Returns:
            Inpainted image as numpy array
        """
        ...

    @abstractmethod
    def create_mask(
        self,
        image_path: str,
        bbox: List[int],
        text_bbox: List[int],
    ) -> np.ndarray:
        """
        Create a mask for text removal.

        Args:
            image_path: Path to the comic page image
            bbox: Bubble bounding box [x1, y1, x2, y2]
            text_bbox: Text bounding box [x1, y1, x2, y2]

        Returns:
            Binary mask as numpy array
        """
        ...

    @abstractmethod
    def get_model_name(self) -> str:
        """
        Get the name/identifier of this inpainter model.

        Returns:
            Model name (e.g., "lama", "aot", "mi_gan")
        """
        ...
