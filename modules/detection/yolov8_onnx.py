import numpy as np
import logging
from typing import List, Tuple

from .base import DetectionEngine
from ..utils.download import ModelDownloader, ModelID
from ..utils.device import get_providers

logger = logging.getLogger(__name__)


class YOLOv8ONNXDetection(DetectionEngine):
    """YOLOv8-based detection engine for comic text/bubble detection.

    Uses the ultralytics YOLO library to load the comic-speech-bubble-detector
    model.  Falls back to raw ONNX inference if ultralytics is not available.

    The model detects: bubble (0), text_bubble (1), text_free (2).
    """

    def __init__(self, settings=None):
        self.model = None
        self.device = "cpu"
        self.settings = settings
        self.conf_threshold = 0.3
        self.iou_threshold = 0.45

    # ------------------------------------------------------------------ #
    # DetectionEngine interface
    # ------------------------------------------------------------------ #
    def initialize(self, device: str = "cpu") -> None:
        self.device = device
        if self.model is None:
            ModelDownloader.get(ModelID.YOLOV8_COMIC_ONNX)
            model_path = ModelDownloader.primary_path(ModelID.YOLOV8_COMIC_ONNX)
            try:
                from ultralytics import YOLO
                self.model = YOLO(model_path)
                self._use_ultralytics = True
                logger.info("YOLOv8 detector loaded via ultralytics from %s", model_path)
            except ImportError:
                logger.warning(
                    "ultralytics not installed. YOLOv8 detector requires "
                    "'pip install ultralytics'. Falling back to stub."
                )
                self._use_ultralytics = False

    def detect(
        self, image: np.ndarray
    ) -> Tuple[List[np.ndarray], List[np.ndarray], List[int]]:
        """Run detection and return (boxes, scores, classes).

        Args:
            image: BGR/RGB uint8 numpy array [H, W, C].

        Returns:
            boxes   – list of [x1, y1, x2, y2] int arrays (original coords)
            scores  – list of confidence arrays
            classes – list of int class ids
        """
        if not self._use_ultralytics or self.model is None:
            logger.error("YOLOv8 model not available — returning empty detections.")
            return [], [], []

        # Run inference
        results = self.model.predict(
            source=image,
            conf=self.conf_threshold,
            iou=self.iou_threshold,
            device=self.device,
            verbose=False,
        )

        boxes_list: List[np.ndarray] = []
        scores_list: List[np.ndarray] = []
        classes_list: List[int] = []

        if results and len(results) > 0:
            result = results[0]  # single image
            if result.boxes is not None and len(result.boxes) > 0:
                # xyxy in original image coordinates
                xyxy = result.boxes.xyxy.cpu().numpy().astype(np.int32)
                confs = result.boxes.conf.cpu().numpy()
                cls_ids = result.boxes.cls.cpu().numpy().astype(int)

                for i in range(len(xyxy)):
                    boxes_list.append(xyxy[i])
                    scores_list.append(np.array([confs[i]]))
                    classes_list.append(int(cls_ids[i]))

        return boxes_list, scores_list, classes_list
