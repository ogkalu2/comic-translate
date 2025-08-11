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
            self.ocr = PaddleOCR(
                lang=lang, 
                text_detection_model_name='PP-OCRv5_mobile_det',
                text_recognition_model_name='PP-OCRv5_mobile_rec',
                use_doc_orientation_classify=False,  
                use_doc_unwarping=False,  
                use_textline_orientation=False  
            )
        
    def process_image(self, img: np.ndarray, blk_list: list[TextBlock]) -> list[TextBlock]:
        try:
            result = self.ocr.predict(img)
            
            if not result or not result[0]:
                return blk_list
                
            result = result[0]
            
            # Extract bounding boxes and text
            texts_bboxes = []
            texts_string = []
            
            # Handle new PaddleOCR format with structured output
            if isinstance(result, dict) and 'rec_texts' in result and 'rec_boxes' in result:
                # New format: structured dictionary
                rec_texts = result['rec_texts']
                rec_boxes = result['rec_boxes']
                
                for i, (bbox, text) in enumerate(zip(rec_boxes, rec_texts)):
                    # bbox is already in (x1, y1, x2, y2) format
                    texts_bboxes.append((int(bbox[0]), int(bbox[1]), int(bbox[2]), int(bbox[3])))
                    texts_string.append(text)
            else:
                # Old format: list of [bbox, text_info] pairs
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
            import traceback
            traceback.print_exc()
            return blk_list