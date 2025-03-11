import os
import numpy as np

from ..base import OCREngine
from ...utils.textblock import TextBlock, adjust_text_line_coordinates
from ...utils.download import get_models, manga_ocr_data


class MangaOCREngine(OCREngine):
    """OCR engine using MangaOCR for Japanese text."""
    
    def __init__(self):
        self.model = None
        self.device = 'cpu'
        self.expansion_percentage = 5
        self.current_file_dir = os.path.dirname(os.path.abspath(__file__))
        self.project_root = os.path.abspath(os.path.join(self.current_file_dir, '..', '..', '..'))
        
    def initialize(self, device: str = 'cpu', expansion_percentage: int = 5) -> None:
        """
         Initialize the MangaOCR engine.
         
         Args:
             device: Device to use ('cpu' or 'cuda')
             expansion_percentage: Percentage to expand text bounding boxes
         """
        
        from .manga_ocr import MangaOcr

        self.device = device
        self.expansion_percentage = expansion_percentage
        if self.model is None:
            get_models(manga_ocr_data)
            manga_ocr_path = os.path.join(self.project_root, 'models/ocr/manga-ocr-base')
            self.model = MangaOcr(pretrained_model_name_or_path=manga_ocr_path, device=device)
        
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
                    blk.text = self.model(cropped_img)
                else:
                    print('Invalid textbbox to target img')
                    blk.text = ""
            except Exception as e:
                print(f"MangaOCR error on block: {str(e)}")
                blk.text = ""
                
        return blk_list