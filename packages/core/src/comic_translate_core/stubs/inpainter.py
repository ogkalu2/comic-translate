"""
Stub inpainter implementation for testing.
"""

from typing import List, Optional, Tuple

import numpy as np

from ..interfaces import IInpainter


class StubInpainter(IInpainter):
    """
    Stub inpainter that returns the original image unchanged.
    
    Useful for testing the pipeline without actual inpainting models.
    """

    def __init__(self, fill_color: Tuple[int, int, int] = (255, 255, 255)):
        """
        Initialize with optional fill color.

        Args:
            fill_color: RGB color to fill inpainted regions (default: white)
        """
        self.fill_color = fill_color

    def inpaint(
        self,
        image_path: str,
        bbox: List[int],
        mask: Optional[np.ndarray] = None,
    ) -> np.ndarray:
        """
        Return a simple inpainted region (filled with solid color).

        Args:
            image_path: Path to the comic page image
            bbox: Bounding box [x1, y1, x2, y2]
            mask: Optional binary mask (ignored)

        Returns:
            Inpainted region as numpy array
        """
        from PIL import Image
        
        img = np.array(Image.open(image_path))
        x1, y1, x2, y2 = bbox
        
        # Create a copy and fill the region with solid color
        result = img.copy()
        result[y1:y2, x1:x2] = self.fill_color
        
        return result

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
            masks: Optional list of binary masks (ignored)

        Returns:
            Inpainted image as numpy array
        """
        from PIL import Image
        
        img = np.array(Image.open(image_path))
        result = img.copy()
        
        for bbox in bboxes:
            x1, y1, x2, y2 = bbox
            result[y1:y2, x1:x2] = self.fill_color
        
        return result

    def create_mask(
        self,
        image_path: str,
        bbox: List[int],
        text_bbox: List[int],
    ) -> np.ndarray:
        """
        Create a simple mask for text removal.

        Args:
            image_path: Path to the comic page image
            bbox: Bubble bounding box [x1, y1, x2, y2]
            text_bbox: Text bounding box [x1, y1, x2, y2]

        Returns:
            Binary mask as numpy array
        """
        from PIL import Image
        
        img = np.array(Image.open(image_path))
        height, width = img.shape[:2]
        
        # Create mask with ones in the text region
        mask = np.zeros((height, width), dtype=np.uint8)
        x1, y1, x2, y2 = text_bbox
        mask[y1:y2, x1:x2] = 255
        
        return mask

    def get_model_name(self) -> str:
        """
        Get the name/identifier of this inpainter model.

        Returns:
            Model name
        """
        return "stub"
