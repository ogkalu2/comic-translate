import numpy as np

from .base import OCREngine
from ..utils.textblock import TextBlock
from ..utils.pipeline_utils import lists_to_blk_list


class PaddleOCREngine(OCREngine):
    """OCR engine using PaddleOCR for Chinese text."""
    
    def __init__(self):
        self.ocr = None
        
    def initialize(self, lang: str = 'ch') -> None:
        """
        Initialize the PaddleOCR engine.
        
        Args:
            lang: Language code for OCR
        """

        from paddleocr import PaddleOCR

        if self.ocr is None:
            self.ocr = PaddleOCR(lang=lang)
        
    def process_image(self, img: np.ndarray, blk_list: list[TextBlock]) -> list[TextBlock]:
        try:
            result = self.ocr.ocr(img)
            
            if not result or not result[0]:
                return blk_list
                
            result = result[0]
            
            # Extract bounding boxes and text
            texts_bboxes = []
            texts_string = []
            
            for line in result:
                bbox, text_info = line
                # Convert from points [(x1,y1), (x2,y1), (x2,y2), (x1,y2)] to (x1,y1,x2,y2)
                x1, y1 = bbox[0]
                x2, y2 = bbox[2]
                texts_bboxes.append((x1, y1, x2, y2))
                texts_string.append(text_info[0])
                
            return lists_to_blk_list(blk_list, texts_bboxes, texts_string)
        
        except Exception as e:
            print(f"PaddleOCR error: {str(e)}")
            return blk_list