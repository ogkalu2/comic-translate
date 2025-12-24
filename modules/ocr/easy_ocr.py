import numpy as np

from .base import OCREngine
from ..utils.textblock import TextBlock, adjust_text_line_coordinates


class EasyOCREngine(OCREngine):
    """OCR engine using EasyOCR for English text."""
    
    def __init__(self):
        self.reader = None
        self.language = ['en']
        self.gpu_enabled = False
        self.expansion_percentage = 5
        
    def initialize(self, languages: list[str] = None, use_gpu: bool = False, 
                  expansion_percentage: int = 5) -> None:
        """
        Initialize the EasyOCR engine.
        
        Args:
            languages: List of language codes for OCR
            use_gpu: Whether to use GPU acceleration
            expansion_percentage: Percentage to expand text bounding boxes
        """

        import easyocr
        self.language = languages or ['en']
        self.gpu_enabled = use_gpu
        self.expansion_percentage = expansion_percentage
        
        # Initialize model if not already loaded
        if self.reader is None:
            self.reader = easyocr.Reader(self.language, gpu=self.gpu_enabled)
        
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
                    result = self.reader.readtext(cropped_img, paragraph=True)
                    texts = [r[1] for r in result if r is not None]
                    blk.text = ' '.join(texts)
                else:
                    print('Invalid textbbox to target img')
                    blk.text = ""
            except Exception as e:
                print(f"EasyOCR error on block: {str(e)}")
                blk.text = ""
                
        return blk_list