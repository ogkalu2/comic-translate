import numpy as np

from modules.ocr.base import OCREngine
from modules.utils.textblock import TextBlock, adjust_text_line_coordinates
from modules.utils.download import ModelDownloader, ModelID


class PororoOCREngine(OCREngine):
    """OCR engine using PororoOCR for Korean text."""
    
    def __init__(self):
        self.model = None
        self.expansion_percentage = 5
        self.device = None
        
    def initialize(
        self, 
        lang: str = 'ko', 
        expansion_percentage: int = 5, 
        device: str = 'cpu'
    ) -> None:
        """
        Initialize the PororoOCR engine.
        
        Args:
            lang: Language code for OCR model - default is 'ko' (Korean)
            expansion_percentage: Percentage to expand text bounding boxes
            device: Device to run the model on ('cpu', 'cuda', etc.). If None, auto-detects.
        """

        from .main import PororoOcr

        self.expansion_percentage = expansion_percentage
        self.device = device
        if self.model is None:
            ModelDownloader.get(ModelID.PORORO)
            self.model = PororoOcr(lang=lang, device=device)
        
    def process_image(self, img: np.ndarray, blk_list: list[TextBlock]) -> list[TextBlock]:
        for blk in blk_list:
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
                
        return blk_list