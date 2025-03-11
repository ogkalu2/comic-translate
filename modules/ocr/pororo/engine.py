import numpy as np

from ..base import OCREngine
from ...utils.textblock import TextBlock, adjust_text_line_coordinates
from ...utils.download import get_models, pororo_data


class PororoOCREngine(OCREngine):
    """OCR engine using PororoOCR for Korean text."""
    
    def __init__(self):
        self.model = None
        self.expansion_percentage = 5
        
    def initialize(self, lang: str = 'ko', expansion_percentage: int = 5) -> None:
        """
        Initialize the PororoOCR engine.
        
        Args:
            lang: Language code for OCR model - default is 'ko' (Korean)
            expansion_percentage: Percentage to expand text bounding boxes
        """

        from .main import PororoOcr

        self.expansion_percentage = expansion_percentage
        if self.model is None:
            get_models(pororo_data)
            self.model = PororoOcr(lang=lang)
        
    def process_image(self, img: np.ndarray, blk_list: list[TextBlock]) -> list[TextBlock]:
        for blk in blk_list:
            try:
                # Get box coordinates
                if blk.bubble_xyxy is not None:
                    x1, y1, x2, y2 = blk.bubble_xyxy
                else:
                    x1, y1, x2, y2 = adjust_text_line_coordinates(
                        blk.xyxy, 
                        self.expansion_percentage, 
                        self.expansion_percentage, 
                        img
                    )
                
                # Check if coordinates are valid
                if x1 < x2 and y1 < y2 and x1 >= 0 and y1 >= 0 and x2 <= img.shape[1] and y2 <= img.shape[0]:
                    # Crop image and run OCR
                    cropped_img = img[y1:y2, x1:x2]
                    self.model.run_ocr(cropped_img)
                    result = self.model.get_ocr_result()
                    descriptions = result.get('description', [])
                    blk.text = ' '.join(descriptions)
                else:
                    print('Invalid textbbox to target img')
                    blk.text = ""
            except Exception as e:
                print(f"PororoOCR error on block: {str(e)}")
                blk.text = ""
                
        return blk_list