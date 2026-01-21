import logging
from typing import List
import numpy as np

from .base import OCREngine
from ..utils.textblock import TextBlock
from ..utils.textblock import lists_to_blk_list

logger = logging.getLogger(__name__)


class RapidOCREngine(OCREngine):
    """OCR engine using RapidOCR.

    This engine leverages RapidOCR's decoupled detector/recognizer pipeline
    and supports PaddleOCR-converted models without the heavy Paddle runtime.
    """

    def __init__(self) -> None:
        self._engine = None
        self._params = {}

    def initialize(self, lang: str = 'ch', use_gpu: bool = False) -> None:
        """Initialize the RapidOCR engine.

        Args:
            lang: Recognition language key for RapidOCR Rec.lang_type.
        """

        from rapidocr import RapidOCR, EngineType, LangDet, \
            LangRec, ModelType, OCRVersion

        det_lang = LangDet.CH

        lang_map = {
            'en': LangRec.EN,
            'fr': LangRec.LATIN,
            'es': LangRec.LATIN,
            'it': LangRec.LATIN,
            'de': LangRec.LATIN,
            'nl': LangRec.LATIN,

            'ja': LangRec.CH,
            'ch': LangRec.CH,

            'ru': LangRec.ESLAV,
            'ko': LangRec.KOREAN,

        }

        rec_lang = lang_map.get(lang.lower(), LangRec.LATIN)

        self._params = {
            'Det.engine_type': EngineType.ONNXRUNTIME,
            'Det.lang_type': det_lang,
            'Det.model_type': ModelType.MOBILE,
            'Det.ocr_version': OCRVersion.PPOCRV5,
            'Det.use_dilation': False,

            'Cls.engine_type': EngineType.ONNXRUNTIME,
            'Cls.model_type': ModelType.MOBILE,
            'Cls.ocr_version': OCRVersion.PPOCRV4,

            'Rec.engine_type': EngineType.ONNXRUNTIME,
            'Rec.lang_type': rec_lang,
            "Rec.model_type": ModelType.MOBILE,
            "Rec.ocr_version": OCRVersion.PPOCRV5,
        }

        if use_gpu:
            self._params.update({
                "EngineConfig.onnxruntime.use_cuda": True,
            })

        self._engine = RapidOCR(params=self._params)

    def process_image(self, img: np.ndarray, blk_list: List[TextBlock]) -> List[TextBlock]:
        """Run OCR on the image and attach text to blocks.

        RapidOCR returns a dataclass-like result with:
          - boxes: ndarray of shape (N, 4, 2)
          - txts: tuple[str] of length N
        We'll convert boxes to (x1, y1, x2, y2) per line and map into TextBlocks.
        """
        if not self._engine:
            logger.warning("RapidOCR engine is not initialized; skipping OCR.")
            return blk_list

        result = self._engine(img)

        if result is None or not hasattr(result, 'boxes') or not hasattr(result, 'txts'):
            logger.debug("RapidOCR returned empty or unexpected result: %s", type(result))
            return blk_list

        boxes = result.boxes  # (N, 4, 2)
        txts = result.txts    # Tuple[str]

        if boxes is None or txts is None or len(txts) == 0:
            return blk_list

        # Convert quadrilateral to axis-aligned bbox
        texts_bboxes = []
        texts_string = []
        
        for i, quad in enumerate(boxes):
            # quad is 4x2 (x,y)
            xs = quad[:, 0]
            ys = quad[:, 1]
            x1 = int(np.floor(xs.min()))
            y1 = int(np.floor(ys.min()))
            x2 = int(np.ceil(xs.max()))
            y2 = int(np.ceil(ys.max()))
            texts_bboxes.append((x1, y1, x2, y2))
            # may return fewer boxes than txts in rare cases
            if i < len(txts):
                texts_string.append(txts[i])

        if not texts_bboxes or not texts_string:
            return blk_list

        return lists_to_blk_list(blk_list, texts_bboxes, texts_string)
