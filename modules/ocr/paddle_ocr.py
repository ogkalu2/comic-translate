import numpy as np
import logging

from .base import OCREngine
from ..utils.textblock import TextBlock
from ..utils.textblock import lists_to_blk_list

logger = logging.getLogger(__name__)


class PaddleOCREngine(OCREngine):
    """OCR engine using PaddleOCR for Chinese text."""
    
    def __init__(self):
        self.ocr = None
        self._use_predict_api = False
        self._legacy_api = False
        
    def initialize(self, lang: str = 'ch') -> None:
        """
        Initialize the PaddleOCR engine.
        
        Args:
            lang: Language code for OCR
        """

        if self.ocr is not None:
            return

        # Try initializing PaddleOCR with minimal, broadly compatible arguments.
        # If that fails (e.g., due to Paddle/PaddleOCR API mismatches), fall back
        # to older API signatures.
        try:
            from paddleocr import PaddleOCR  # v3.x pipeline style
        except Exception as e:
            logger.warning("PaddleOCR import failed: %s", e)
            PaddleOCR = None
        try:
            # Legacy v2.x API location
            from paddleocr.paddleocr import PaddleOCR as LegacyPaddleOCR  # type: ignore
        except Exception:
            LegacyPaddleOCR = None

        # Attempt new/standard initialization first
        if PaddleOCR is not None:
            try:
                self.ocr = PaddleOCR(
                    lang=lang, 
                    text_detection_model_name='PP-OCRv5_mobile_det',
                    text_recognition_model_name='PP-OCRv5_mobile_rec',
                    use_doc_orientation_classify=False,  
                    use_doc_unwarping=False,  
                    use_textline_orientation=False  
                )
                self._use_predict_api = hasattr(self.ocr, 'predict')
                self._legacy_api = hasattr(self.ocr, 'ocr')
                return
            except Exception as e:
                logger.warning("PaddleOCR initialization failed: %s", e)

            # Try older/common signature used by 2.x series
            if LegacyPaddleOCR is not None:
                try:
                    self.ocr = LegacyPaddleOCR(use_angle_cls=False, lang=lang)
                    self._use_predict_api = False
                    self._legacy_api = True
                    return
                except Exception as e:
                    logger.warning("PaddleOCR legacy initialization failed: %s", e)
            else:
                logger.warning("Legacy PaddleOCR module not available")

        # If new import failed but legacy module exists, try legacy directly
        if self.ocr is None and LegacyPaddleOCR is not None:
            try:
                self.ocr = LegacyPaddleOCR(use_angle_cls=False, lang=lang)
                self._use_predict_api = False
                self._legacy_api = True
                return
            except Exception as e:
                logger.warning("Direct legacy PaddleOCR init failed: %s", e)
        
    def process_image(self, img: np.ndarray, blk_list: list[TextBlock]) -> list[TextBlock]:
        if self.ocr is None:
            return blk_list

        # Newer PaddleOCR pipeline API
        if self._use_predict_api:
            result = self.ocr.predict(img)
        # Legacy PaddleOCR API (2.x)
        elif self._legacy_api:
            result = self.ocr.ocr(img, det=True, rec=True)
        else:
            return blk_list
        
        if not result or not result[0]:
            return blk_list
            
        # Normalize result to a per-line list when using list-based outputs
        # Case A: New pipeline often returns [ { 'rec_texts': ..., 'rec_boxes': ... } ]
        if isinstance(result, list) and len(result) > 0 and isinstance(result[0], dict) and 'rec_texts' in result[0]:
            result = result[0]
        # Case B: Legacy API may return [[line, line, ...]] or [line, line, ...]
        elif isinstance(result, list) and len(result) > 0 and isinstance(result[0], list):
            first_elem = result[0]
            # If first_elem looks like a line pair [bbox, text_info], then result is already per-line
            looks_like_line = (
                isinstance(first_elem, list) and len(first_elem) == 2 and isinstance(first_elem[0], (list, tuple))
            )
            # Otherwise, assume result[0] is the per-line list
            if not looks_like_line:
                result = first_elem
        
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