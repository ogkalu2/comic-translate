from abc import ABC, abstractmethod
import numpy as np
from typing import Optional

from modules.utils.textblock import TextBlock
from .utils.geometry import does_rectangle_fit, do_rectangles_overlap, \
    merge_overlapping_boxes
from .font.engine import FontEngineFactory
from .font.foreground_color import estimate_text_foreground_color
from .utils.content import filter_and_fix_bboxes


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
        
        # Process text boxes
        if len(text_boxes) > 0:
            for txt_idx, txt_box in enumerate(text_boxes):
                font_attrs = {}
                crop = None
                # Calculate font attributes using FontEngine
                try:
                    x1, y1, x2, y2 = map(int, txt_box)
                    # Ensure coordinates are within image bounds
                    h, w = image.shape[:2]
                    x1 = max(0, x1)
                    y1 = max(0, y1)
                    x2 = min(w, x2)
                    y2 = min(h, y2)
                    
                    if x2 > x1 and y2 > y1:
                        crop = image[y1:y2, x1:x2]
                        font_engine = FontEngineFactory.create_engine(self.settings, backend='onnx')
                        font_attrs = font_engine.process(crop)
                except Exception as e:
                    print(f"Failed to detect font attributes for text block {txt_idx}: {e}")

                direction = font_attrs.get('direction', '')
                text_color = tuple(font_attrs.get('text_color', ()))
                try:
                    est = estimate_text_foreground_color(crop) if crop is not None else None
                    if est is not None:
                        text_color = est.rgb
                except Exception:
                    pass
                angle = 0
                # angle = -font_attrs.get('angle', 0)
                # if abs(angle) < 10:
                #     angle = 0

                # If no bubble boxes, all text is free text
                if len(bubble_boxes) == 0:
                    text_blocks.append(
                        TextBlock(
                            text_bbox=txt_box,
                            text_class='text_free',
                            direction=direction,
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
                                direction=direction,
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
                                direction=direction,
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
                            direction=direction,
                            font_color=text_color,
                        )
                    )
        
        return text_blocks
    
