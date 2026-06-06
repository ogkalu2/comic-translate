from abc import ABC, abstractmethod
import numpy as np
from typing import Optional

from ..utils.textblock import TextBlock
from .utils.geometry import does_rectangle_fit, do_rectangles_overlap, \
    merge_overlapping_boxes
from .font.engine import extract_foreground_color
from .heuristic_lines import annotate_blocks_with_heuristic_lines
from .backend import resolve_detection_backend
from modules.utils.device import resolve_device
from .utils.content import filter_and_fix_bboxes


class DetectionEngine(ABC):
    """
    Abstract base class for all detection engines.
    Each model implementation should inherit from this class.
    """
    
    def __init__(self, settings=None):
        self.settings = settings
        self.backend = resolve_detection_backend()
    
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
        
    def create_text_blocks(
        self, 
        image: np.ndarray, 
        text_boxes: np.ndarray,
        bubble_boxes: Optional[np.ndarray] = None
    ) -> list[TextBlock]:
        
        text_boxes = filter_and_fix_bboxes(text_boxes, image.shape)
        bubble_boxes = filter_and_fix_bboxes(bubble_boxes, image.shape)
        text_boxes = merge_overlapping_boxes(text_boxes)

        text_blocks = []
        text_matched = [False] * len(text_boxes)  # Track matched text boxes
        
        # Set bubble_boxes to empty array if None
        if bubble_boxes is None:
            bubble_boxes = np.array([])

        if len(text_boxes) == 0:
            return text_blocks

        # Collect text foreground color without running the expensive font model.
        h, w = image.shape[:2]
        text_colors_per_box: list[tuple] = [()] * len(text_boxes)
        for txt_idx, txt_box in enumerate(text_boxes):
            x1, y1, x2, y2 = map(int, txt_box)
            x1 = max(0, x1); y1 = max(0, y1)
            x2 = min(w, x2); y2 = min(h, y2)
            if x2 > x1 and y2 > y1:
                text_color = extract_foreground_color(image[y1:y2, x1:x2])
                if text_color is not None:
                    text_colors_per_box[txt_idx] = tuple(text_color)

        # Build TextBlock objects using pre-computed font attrs
        for txt_idx, txt_box in enumerate(text_boxes):
            text_color = text_colors_per_box[txt_idx]

            # If no bubble boxes, all text is free text
            if len(bubble_boxes) == 0:
                text_blocks.append(
                        TextBlock(
                            text_bbox=txt_box,
                            text_class='text_free',
                            font_color=text_color,
                        )
                )
                continue
            
            for bble_box in bubble_boxes:
                if bble_box is None:
                    continue
                if does_rectangle_fit(bble_box, txt_box):
                    # Text is inside a bubble
                    text_blocks.append(
                        TextBlock(
                            text_bbox=txt_box,
                            bubble_bbox=bble_box,
                            text_class='text_bubble',
                            font_color=text_color,
                        )
                    )
                    text_matched[txt_idx] = True  
                    break
                elif do_rectangles_overlap(bble_box, txt_box):
                    # Text overlaps with a bubble
                    text_blocks.append(
                        TextBlock(
                            text_bbox=txt_box,
                            bubble_bbox=bble_box,
                            text_class='text_bubble',
                            font_color=text_color,
                        )
                    )
                    text_matched[txt_idx] = True  
                    break
            
            if not text_matched[txt_idx]:
                text_blocks.append(
                    TextBlock(
                        text_bbox=txt_box,
                        text_class='text_free',
                        font_color=text_color,
                    )
                )
        
        try:
            backend = resolve_detection_backend(getattr(self, "backend", None))
            device = resolve_device(self.settings.is_gpu_enabled(), backend) if self.settings else "cpu"
            _ = backend, device
            annotate_blocks_with_heuristic_lines(image, text_blocks)
        except Exception as e:
            print(f"Failed to build heuristic text lines: {e}")

        return text_blocks
