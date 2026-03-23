import os
import numpy as np
import re
import jaconv
import logging

from modules.ocr.base import OCREngine
from modules.utils.textblock import TextBlock, adjust_text_line_coordinates
from modules.utils.download import ModelDownloader, ModelID, models_base_dir
from modules.utils.torch_autocast import TorchAutocastMixin

logger = logging.getLogger(__name__)


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

class MangaOcr(TorchAutocastMixin):
    def __init__(self, pretrained_model_name_or_path=manga_ocr_path, device='cpu'):
        import torch
        from transformers import AutoTokenizer, ViTImageProcessor, VisionEncoderDecoderModel

        self.processor = ViTImageProcessor.from_pretrained(pretrained_model_name_or_path)
        self.tokenizer = AutoTokenizer.from_pretrained(pretrained_model_name_or_path)
        self.model = VisionEncoderDecoderModel.from_pretrained(pretrained_model_name_or_path)
        self.setup_torch_autocast(torch, device)
        self.to(device)

    def to(self, device):
        self.model.to(device)

    def __call__(self, img: np.ndarray):
        import torch

        x = self.processor(img, return_tensors="pt").pixel_values.squeeze()
        with torch.inference_mode():
            x = self.run_with_torch_autocast(
                torch_module=torch,
                fn=lambda: self.model.generate(x[None].to(self.model.device))[0].cpu(),
                logger=logger,
                engine_name=self.__class__.__name__,
            )
        x = self.tokenizer.decode(x, skip_special_tokens=True)
        x = post_process(x)
        return x

def post_process(text):
    text = ''.join(text.split())
    text = text.replace('…', '...')
    text = re.sub('[・.]{2,}', lambda x: (x.end() - x.start()) * '.', text)
    text = jaconv.h2z(text, ascii=True, digit=True)

    return text
