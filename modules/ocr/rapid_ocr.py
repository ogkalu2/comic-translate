import logging
import torch
from typing import List
import numpy as np

from .base import OCREngine
from ..utils.textblock import TextBlock
from ..utils.pipeline_utils import lists_to_blk_list

logger = logging.getLogger(__name__)


class RapidOCREngine(OCREngine):
    """OCR engine using RapidOCR.

    This engine leverages RapidOCR's decoupled detector/recognizer pipeline
    and supports PaddleOCR-converted models without the heavy Paddle runtime.
    """

    def __init__(self) -> None:
        self._engine = None
        self._initialized = False
        self._params = {}

    def initialize(self, lang: str = 'ch', use_gpu: bool = False) -> None:
        """Initialize the RapidOCR engine.

        Args:
            lang: Recognition language key for RapidOCR Rec.lang_type.
        """
        if self._initialized:
            return

        try:
            # RapidOCR is the high-level wrapper. It defaults to ONNXRuntime.
            from rapidocr import RapidOCR, EngineType, LangDet, \
                LangRec, ModelType, OCRVersion
            # Prefer robust detection across scripts; use multi-language det
            # For Chinese we keep Det.lang_type as 'ch'; for others, 'multi'
            det_lang = LangDet.CH if lang == 'ch' else LangDet.MULTI
            rec_lang = LangRec.CH if lang == 'ch' else LangRec.CYRILLIC

            # Build minimal params; RapidOCR will auto-download models.
            self._params = {
                'Det.engine_type': EngineType.TORCH,
                'Det.lang_type': det_lang,
                'Det.model_type': ModelType.MOBILE,
                'Det.ocr_version': OCRVersion.PPOCRV5,
                'Cls.engine_type': EngineType.TORCH,
                'Rec.engine_type': EngineType.TORCH,
                'Rec.lang_type': rec_lang,
                "Rec.model_type": ModelType.MOBILE,
                "Rec.ocr_version": OCRVersion.PPOCRV5,
            }

            if use_gpu and torch.cuda.is_available():
                self._params.update({
                    "EngineConfig.torch.use_cuda": True,
                    "EngineConfig.torch.gpu_id": 0,
                })

            self._engine = RapidOCR(params=self._params)
            self._initialized = True
            logger.info("RapidOCR initialized with params: %s", self._params)
        except Exception as e:
            logger.error("Failed to initialize RapidOCR: %s", e)
            self._engine = None
            self._initialized = False

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

        # RapidOCR accepts ndarray; it internally converts via PIL.
        result = self._engine(img)

        # Defensive: ensure expected attributes exist
        if result is None or not hasattr(result, 'boxes') or not hasattr(result, 'txts'):
            logger.debug("RapidOCR returned empty or unexpected result: %s", type(result))
            return blk_list

        boxes = result.boxes  # (N, 4, 2)
        txts = result.txts    # Tuple[str]

        if boxes is None or txts is None or len(txts) == 0:
            return blk_list

        # Convert quadrilateral to axis-aligned bbox for our pipeline
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
            # Some engines may return fewer boxes than txts in rare cases
            if i < len(txts):
                texts_string.append(txts[i])

        if not texts_bboxes or not texts_string:
            return blk_list

        return lists_to_blk_list(blk_list, texts_bboxes, texts_string)
