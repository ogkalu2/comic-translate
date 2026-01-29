import os
import numpy as np
import re
import jaconv
from transformers import ViTImageProcessor, AutoTokenizer, \
    VisionEncoderDecoderModel, GenerationMixin
import torch

from modules.ocr.base import OCREngine
from modules.utils.textblock import TextBlock, adjust_text_line_coordinates
from modules.utils.download import ModelDownloader, ModelID, models_base_dir


class MangaOCREngine(OCREngine):
    """OCR engine using MangaOCR for Japanese text."""
    
    def __init__(self):
        self.model = None
        self.device = 'cpu'
        self.expansion_percentage = 5
        
    def initialize(self, device: str = 'cpu', expansion_percentage: int = 5) -> None:
        """
         Initialize the MangaOCR engine.
         
         Args:
             device: Device to use ('cpu' or 'cuda')
             expansion_percentage: Percentage to expand text bounding boxes
         """

        self.device = device
        self.expansion_percentage = expansion_percentage
        if self.model is None:
            ModelDownloader.get(ModelID.MANGA_OCR_BASE)
            manga_ocr_path = os.path.join(models_base_dir, 'ocr', 'manga-ocr-base')
            self.model = MangaOcr(pretrained_model_name_or_path=manga_ocr_path, device=device)
        
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
                blk.text = self.model(cropped_img)
            else:
                print('Invalid textbbox to target img')
                blk.text = ""
                
        return blk_list


# modified from https://github.com/kha-white/manga-ocr/blob/master/manga_ocr/ocr.py
# modified from https://github.com/kha-white/manga-ocr/blob/master/manga_ocr/ocr.py
manga_ocr_path = os.path.join(models_base_dir, 'ocr', 'manga-ocr-base')


class MangaOcrModel(VisionEncoderDecoderModel, GenerationMixin):
    pass

class MangaOcr:
    def __init__(self, pretrained_model_name_or_path=manga_ocr_path, device='cpu'):
        self.processor = ViTImageProcessor.from_pretrained(pretrained_model_name_or_path)
        self.tokenizer = AutoTokenizer.from_pretrained(pretrained_model_name_or_path)
        self.model = MangaOcrModel.from_pretrained(pretrained_model_name_or_path)
        self.to(device)

    def to(self, device):
        self.model.to(device)

    @torch.no_grad()
    def __call__(self, img: np.ndarray):
        x = self.processor(img, return_tensors="pt").pixel_values.squeeze()
        x = self.model.generate(x[None].to(self.model.device))[0].cpu()
        x = self.tokenizer.decode(x, skip_special_tokens=True)
        x = post_process(x)
        return x

def post_process(text):
    text = ''.join(text.split())
    text = text.replace('…', '...')
    text = re.sub('[・.]{2,}', lambda x: (x.end() - x.start()) * '.', text)
    text = jaconv.h2z(text, ascii=True, digit=True)

    return text