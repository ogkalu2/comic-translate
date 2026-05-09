import numpy as np

from modules.ocr.base import OCREngine
from modules.utils.textblock import TextBlock, adjust_text_line_coordinates
from modules.utils.download import ModelDownloader, ModelID
from modules.utils.language_utils import is_no_space_lang
from .pororo.models.brainOCR.utils import reformat_input


class PororoOCREngine(OCREngine):
    """OCR engine using PororoOCR for Korean text."""
    
    def __init__(self):
        self.model = None
        self.expansion_percentage = 5
        self.device = None
        self.use_text_lines = True
        
    def initialize(
        self, 
        lang: str = 'ko', 
        expansion_percentage: int = 5, 
        device: str = 'cpu',
        use_text_lines: bool = True,
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
        self.use_text_lines = use_text_lines
        if self.model is None:
            ModelDownloader.get(ModelID.PORORO)
            self.model = PororoOcr(lang=lang, device=device, use_text_lines=use_text_lines)
        
    def process_image(self, img: np.ndarray, blk_list: list[TextBlock]) -> list[TextBlock]:
        if self.use_text_lines and any(getattr(blk, 'lines', None) for blk in blk_list):
            _, img_cv_grey = reformat_input(img)
            reader = _reader_from_pororo_ocr(self.model)
            if reader is not None:
                _set_reader_recognition_defaults(reader.opt2val)
                for blk in blk_list:
                    lines = getattr(blk, 'lines', None) or [blk.xyxy]
                    texts = []
                    for line in lines:
                        crop = _crop_line_grey(img_cv_grey, line)
                        if crop is None or crop.size == 0:
                            continue
                        result = reader.recognize(crop, None, None, reader.opt2val)
                        texts.extend(text.strip() for _, text, _ in result if text and text.strip())
                    blk.texts = texts
                    blk.text = ''.join(texts) if is_no_space_lang(getattr(blk, 'source_lang', '')) else ' '.join(texts)
                return blk_list

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


def _reader_from_pororo_ocr(model):
    ocr_task = getattr(model, '_ocr', None)
    return getattr(ocr_task, '_model', None)


def _set_reader_recognition_defaults(opt2val: dict) -> None:
    opt2val.setdefault("batch_size", 1)
    opt2val.setdefault("n_workers", 0)
    opt2val.setdefault("contrast_ths", 0.1)
    opt2val.setdefault("adjust_contrast", 0.5)
    opt2val["skip_details"] = False
    opt2val["paragraph"] = False


def _crop_line_grey(img_cv_grey: np.ndarray, line) -> np.ndarray | None:
    arr = np.asarray(line)
    if arr.ndim == 2 and arr.shape[0] >= 4 and arr.shape[1] == 2:
        pts = arr.astype(np.float32)
        x1 = int(np.floor(pts[:, 0].min()))
        y1 = int(np.floor(pts[:, 1].min()))
        x2 = int(np.ceil(pts[:, 0].max()))
        y2 = int(np.ceil(pts[:, 1].max()))
    elif arr.size == 4:
        x1, y1, x2, y2 = [int(round(float(v))) for v in arr.reshape(-1)[:4]]
    else:
        return None

    x1 = max(0, min(img_cv_grey.shape[1], x1))
    x2 = max(0, min(img_cv_grey.shape[1], x2))
    y1 = max(0, min(img_cv_grey.shape[0], y1))
    y2 = max(0, min(img_cv_grey.shape[0], y2))
    if x2 <= x1 or y2 <= y1:
        return None
    crop = img_cv_grey[y1:y2, x1:x2]
    h, w = crop.shape[:2]
    if h > 0 and w > 0 and h / float(w) >= 1.5:
        crop = np.rot90(crop)
    return crop
