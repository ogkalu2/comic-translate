# modified from https://github.com/kha-white/manga-ocr/blob/master/manga_ocr/ocr.py
import re
import jaconv
from transformers import ViTImageProcessor, AutoTokenizer, VisionEncoderDecoderModel, GenerationMixin
import numpy as np
import torch

MANGA_OCR_PATH = r'models/ocr/manga-ocr-base'
class MangaOcrModel(VisionEncoderDecoderModel, GenerationMixin):
    pass

class MangaOcr:
    def __init__(self, pretrained_model_name_or_path=MANGA_OCR_PATH, device='cpu'):
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


