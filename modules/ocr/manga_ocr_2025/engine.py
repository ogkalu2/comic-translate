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


class MangaOCR2025Engine(OCREngine):
    """OCR engine using the upgraded manga-ocr-base-2025 model for Japanese text.

    This is the 2025 fine-tuned version of kha-white/manga-ocr, offering
    improved accuracy on modern manga fonts and layouts.  Uses TrOCRProcessor
    instead of ViTImageProcessor from the original model.
    """

    def __init__(self):
        self.model = None
        self.device = 'cpu'
        self.expansion_percentage = 5

    def initialize(self, device: str = 'cpu', expansion_percentage: int = 5) -> None:
        self.device = device
        self.expansion_percentage = expansion_percentage
        if self.model is None:
            ModelDownloader.get(ModelID.MANGA_OCR_2025)
            model_path = os.path.join(models_base_dir, 'ocr', 'manga-ocr-base-2025')
            self.model = MangaOcr2025(pretrained_model_name_or_path=model_path, device=device)

    def process_image(self, img: np.ndarray, blk_list: list[TextBlock]) -> list[TextBlock]:
        for blk in blk_list:
            if blk.bubble_xyxy is not None:
                x1, y1, x2, y2 = blk.bubble_xyxy
            else:
                x1, y1, x2, y2 = adjust_text_line_coordinates(
                    blk.xyxy,
                    self.expansion_percentage,
                    self.expansion_percentage,
                    img
                )

            if x1 < x2 and y1 < y2 and x1 >= 0 and y1 >= 0 and x2 <= img.shape[1] and y2 <= img.shape[0]:
                cropped_img = img[y1:y2, x1:x2]
                blk.text = self.model(cropped_img)
            else:
                print('Invalid textbbox to target img')
                blk.text = ""

        return blk_list


class MangaOcr2025(TorchAutocastMixin):
    """Wrapper around the manga-ocr-base-2025 VisionEncoderDecoderModel.

    Uses TrOCRProcessor (replacing the older ViTImageProcessor) for
    preprocessing, and VisionEncoderDecoderModel for generation.
    """

    def __init__(self, pretrained_model_name_or_path: str, device: str = 'cpu'):
        import torch
        from transformers import TrOCRProcessor, VisionEncoderDecoderModel

        self.processor = TrOCRProcessor.from_pretrained(pretrained_model_name_or_path)
        self.model = VisionEncoderDecoderModel.from_pretrained(pretrained_model_name_or_path)
        self.setup_torch_autocast(torch, device)
        self.to(device)

    def to(self, device):
        self.model.to(device)

    def __call__(self, img: np.ndarray) -> str:
        import torch

        x = self.processor(img, return_tensors="pt").pixel_values.squeeze()
        with torch.inference_mode():
            x = self.run_with_torch_autocast(
                torch_module=torch,
                fn=lambda: self.model.generate(x[None].to(self.model.device))[0].cpu(),
                logger=logger,
                engine_name=self.__class__.__name__,
            )
        x = self.processor.batch_decode([x], skip_special_tokens=True)[0]
        x = post_process(x)
        return x


def post_process(text: str) -> str:
    text = ''.join(text.split())
    text = text.replace('…', '...')
    text = re.sub('[・.]{2,}', lambda x: (x.end() - x.start()) * '.', text)
    text = jaconv.h2z(text, ascii=True, digit=True)
    return text
