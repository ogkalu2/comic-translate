"""
Rendering adapter for wrapping rendering package implementations.
"""

from typing import Any, Dict, List, Optional, Tuple
import numpy as np

from ..interfaces.renderer import IRenderer
from ..interfaces.inpainter import IInpainter


class RenderingAdapter:
    """
    Adapter for rendering engines.
    Wraps the rendering package to implement core interfaces.
    """

    def __init__(self, engine_type: str = "default", **kwargs):
        self.engine_type = engine_type
        self._engine = None
        self._kwargs = kwargs

    def _get_engine(self):
        """Lazy load the rendering engine."""
        if self._engine is None:
            from comic_translate_rendering.engine import RenderingEngineFactory
            self._engine = RenderingEngineFactory.create_engine(
                engine_type=self.engine_type,
                **self._kwargs
            )
        return self._engine

    def render(self, img: np.ndarray, blk_list: list, font_size: int = 0, **kwargs) -> np.ndarray:
        """
        Render translated text onto an image.

        Args:
            img: Input image as numpy array
            blk_list: List of text blocks to render
            font_size: Font size for rendering (0 = auto)
            **kwargs: Additional rendering parameters

        Returns:
            Image with rendered text as numpy array
        """
        engine = self._get_engine()
        return engine.render(img, blk_list, font_size, **kwargs)


class InpaintingAdapter:
    """
    Adapter for inpainting engines.
    Wraps the rendering package to implement core interfaces.
    """

    def __init__(self, engine_type: str = "lama", **kwargs):
        self.engine_type = engine_type
        self._engine = None
        self._kwargs = kwargs

    def _get_engine(self):
        """Lazy load the inpainting engine."""
        if self._engine is None:
            from comic_translate_rendering.engine import InpaintingEngineFactory
            self._engine = InpaintingEngineFactory.create_engine(
                engine_type=self.engine_type,
                **self._kwargs
            )
        return self._engine

    def inpaint(self, img: np.ndarray, mask: np.ndarray, **kwargs) -> np.ndarray:
        """
        Inpaint (remove text) from an image.

        Args:
            img: Input image as numpy array
            mask: Binary mask indicating text pixels to remove
            **kwargs: Additional inpainting parameters

        Returns:
            Inpainted image as numpy array
        """
        engine = self._get_engine()
        return engine.inpaint(img, mask, **kwargs)


class RendererAdapter(IRenderer):
    """Adapter implementing IRenderer interface."""

    def __init__(self, engine_type: str = "default", **kwargs):
        self._adapter = RenderingAdapter(engine_type=engine_type, **kwargs)

    def render(
        self,
        image: np.ndarray,
        text: str,
        bbox: List[int],
        font_size: Optional[int] = None,
        font_color: Optional[Tuple[int, int, int]] = None,
    ) -> np.ndarray:
        """Render translated text onto an image within a bounding box."""
        from modules.utils.textblock import TextBlock
        blk = TextBlock()
        blk.text = text
        blk.xyxy = np.array(bbox)

        return self._adapter.render(
            image,
            [blk],
            font_size=font_size or 0
        )

    def render_batch(
        self,
        image: np.ndarray,
        texts: List[str],
        bboxes: List[List[int]],
        font_sizes: Optional[List[int]] = None,
        font_colors: Optional[List[Tuple[int, int, int]]] = None,
    ) -> np.ndarray:
        """Render multiple texts onto an image."""
        from modules.utils.textblock import TextBlock
        blocks = []
        for i, (text, bbox) in enumerate(zip(texts, bboxes)):
            blk = TextBlock()
            blk.text = text
            blk.xyxy = np.array(bbox)
            blocks.append(blk)

        font_size = font_sizes[0] if font_sizes else 0
        return self._adapter.render(image, blocks, font_size=font_size)


class InpainterAdapter(IInpainter):
    """Adapter implementing IInpainter interface."""

    def __init__(self, engine_type: str = "lama", **kwargs):
        self._adapter = InpaintingAdapter(engine_type=engine_type, **kwargs)

    def inpaint(
        self,
        image_path: str,
        bbox: List[int],
        mask: Optional[np.ndarray] = None,
    ) -> np.ndarray:
        """Inpaint (remove text) from a specific region of an image."""
        import cv2
        image = cv2.imread(image_path)
        x1, y1, x2, y2 = bbox

        if mask is None:
            # Create a simple mask from the bbox region
            mask = np.zeros(image.shape[:2], dtype=np.uint8)
            mask[y1:y2, x1:x2] = 255

        return self._adapter.inpaint(image, mask)

    def inpaint_batch(
        self,
        image_path: str,
        bboxes: List[List[int]],
        masks: Optional[List[np.ndarray]] = None,
    ) -> np.ndarray:
        """Inpaint multiple regions of an image."""
        import cv2
        image = cv2.imread(image_path)

        if masks is None:
            # Create masks from bboxes
            masks = []
            for bbox in bboxes:
                x1, y1, x2, y2 = bbox
                mask = np.zeros(image.shape[:2], dtype=np.uint8)
                mask[y1:y2, x1:x2] = 255
                masks.append(mask)

        # Combine all masks
        combined_mask = np.zeros(image.shape[:2], dtype=np.uint8)
        for mask in masks:
            combined_mask = np.maximum(combined_mask, mask)

        return self._adapter.inpaint(image, combined_mask)
