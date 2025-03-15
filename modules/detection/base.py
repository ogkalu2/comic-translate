from abc import ABC, abstractmethod
import numpy as np
from typing import Optional

from ..utils.textblock import TextBlock
from .utils.general import does_rectangle_fit, do_rectangles_overlap, \
      get_inpaint_bboxes, filter_bounding_boxes


class DetectionEngine(ABC):
    """
    Abstract base class for all detection engines.
    Each model implementation should inherit from this class.
    """
    
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
        
    def create_text_blocks(self, image: np.ndarray, 
                          text_boxes: np.ndarray,
                          bubble_boxes: Optional[np.ndarray] = None) -> list[TextBlock]:
        
        text_boxes = filter_bounding_boxes(text_boxes)

        text_blocks = []
        text_matched = [False] * len(text_boxes)  # Track matched text boxes
        
        # Set bubble_boxes to empty array if None
        if bubble_boxes is None:
            bubble_boxes = np.array([])
        
        # Process text boxes
        if len(text_boxes) > 0:
            for txt_idx, txt_box in enumerate(text_boxes):
                # Get inpaint boxes for this text box
                inpaint_boxes = get_inpaint_bboxes(txt_box, image)
                
                # If no bubble boxes, all text is free text
                if len(bubble_boxes) == 0:
                    text_blocks.append(
                        TextBlock(
                            text_bbox=txt_box,
                            text_class='text_free',
                            inpaint_bboxes=inpaint_boxes,
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
                                bubble_xyxy=bble_box,
                                text_class='text_bubble',
                                inpaint_bboxes=inpaint_boxes,
                            )
                        )
                        text_matched[txt_idx] = True  
                        break
                    elif do_rectangles_overlap(bble_box, txt_box):
                        # Text overlaps with a bubble
                        text_blocks.append(
                            TextBlock(
                                text_bbox=txt_box,
                                bubble_xyxy=bble_box,
                                text_class='text_bubble',
                                inpaint_bboxes=inpaint_boxes,
                            )
                        )
                        text_matched[txt_idx] = True  
                        break
                
                if not text_matched[txt_idx]:
                    text_blocks.append(
                        TextBlock(
                            text_bbox=txt_box,
                            text_class='text_free',
                            inpaint_bboxes=inpaint_boxes,
                        )
                    )
        
        return text_blocks
    
