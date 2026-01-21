import numpy as np
import torch

from .base import OCREngine
from ..utils.textblock import TextBlock
from ..utils.textblock import lists_to_blk_list


class DocTROCR(OCREngine):
    """OCR engine using DocTR"""
    
    def __init__(self):
        self.model = None
        self.device = 'cpu'
        
    def initialize(self, device: str = 'cpu') -> None:
        """
         Initialize the DocTR engine.
         
         Args:
             device: Device to use ('cpu' or 'cuda')
         """
        
        from doctr.models import ocr_predictor

        self.device = device
        # Initialize model if not already loaded
        if self.model is None:
            self.model = ocr_predictor(
                det_arch='db_resnet34', 
                reco_arch='parseq', 
                pretrained=True,
            )

            # Move model to appropriate device
            self.model = self.model.to(device)
        
    def process_image(self, img: np.ndarray, blk_list: list[TextBlock]) -> list[TextBlock]:
        # Process whole image with DocTR
        result = self.model([img])
        
        # Extract text and bounding boxes
        texts_bboxes = []
        texts_string = []
        
        # Process result to extract boxes and text
        for page in result.pages:
            h, w = page.dimensions
            for block in page.blocks:
                for line in block.lines:
                    # Get text from line
                    line_text = " ".join(word.value for word in line.words)
                    if not line_text.strip():
                        continue
                        
                    # Get coordinates and normalize to absolute pixel values
                    x_min, y_min = line.geometry[0]
                    x_max, y_max = line.geometry[1]
                    
                    # Convert relative coordinates to absolute pixel coordinates
                    x1 = int(x_min * w)
                    y1 = int(y_min * h)
                    x2 = int(x_max * w)
                    y2 = int(y_max * h)
                    
                    texts_bboxes.append((x1, y1, x2, y2))
                    texts_string.append(line_text)
        
        # Match detected text to provided blocks using lists_to_blk_list
        return lists_to_blk_list(blk_list, texts_bboxes, texts_string)
    
