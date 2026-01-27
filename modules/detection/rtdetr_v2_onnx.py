import os
import numpy as np
from PIL import Image
import onnxruntime as ort
from modules.utils.device import get_providers
from modules.utils.download import ModelDownloader, ModelID

from .base import DetectionEngine
from ..utils.textblock import TextBlock
from .utils.slicer import ImageSlicer


current_file_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.abspath(os.path.join(current_file_dir, '..', '..'))


class RTDetrV2ONNXDetection(DetectionEngine):
    """RT-DETR-v2 ONNX backend detection engine.
    """

    def __init__(self, settings=None):
        super().__init__(settings)
        self.session = None
        self.device = 'cpu'
        self.confidence_threshold = 0.3
        self.model_dir = os.path.join(project_root, 'models', 'detection')

        self.image_slicer = ImageSlicer(
            height_to_width_ratio_threshold=3.5,
            target_slice_ratio=3.0,
            overlap_height_ratio=0.2,
            min_slice_height_ratio=0.7
        )

    def initialize(
        self, 
        device: str = 'cpu', 
        confidence_threshold: float = 0.3, 
    ) -> None:
        
        self.device = device
        self.confidence_threshold = confidence_threshold

        file_path = ModelDownloader.get_file_path(ModelID.RTDETR_V2_ONNX, 'detector.onnx')
        providers = get_providers(self.device)
        self.session = ort.InferenceSession(file_path, providers=providers)

    def detect(self, image: np.ndarray) -> list[TextBlock]:
        bubble_boxes, text_boxes = self.image_slicer.process_slices_for_detection(
            image, self._detect_single_image
        )
        return self.create_text_blocks(image, text_boxes, bubble_boxes)

    def _detect_single_image(self, image: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
        pil_image = Image.fromarray(image)  # image is already in RGB format

        # preprocess to (1,3,H,W) float32
        im_resized = pil_image.resize((640, 640))
        arr = np.asarray(im_resized, dtype=np.float32) / 255.0  # (H,W,3)
        arr = np.transpose(arr, (2, 0, 1))  # (3,H,W)
        im_data = arr[np.newaxis, ...]  # (1,3,H,W)

        w, h = pil_image.size
        orig_size = np.array([[w, h]], dtype=np.int64)

        outputs = self.session.run(None, {
            "images": im_data,
            "orig_target_sizes": orig_size
        })

        # expected outputs: labels, boxes, scores
        labels, boxes, scores = outputs[:3]

        if isinstance(labels, np.ndarray) and labels.ndim == 2 and labels.shape[0] == 1:
            labels = labels[0]
        if isinstance(scores, np.ndarray) and scores.ndim == 2 and scores.shape[0] == 1:
            scores = scores[0]
        if isinstance(boxes, np.ndarray) and boxes.ndim == 3 and boxes.shape[0] == 1:
            boxes = boxes[0]

        bubble_boxes = []
        text_boxes = []
        for lab, box, scr in zip(labels, boxes, scores):
            if float(scr) < float(self.confidence_threshold):
                continue
            x1, y1, x2, y2 = map(int, box)
            label_id = int(lab)
            if label_id == 0:
                bubble_boxes.append([x1, y1, x2, y2])
            elif label_id in [1, 2]:
                text_boxes.append([x1, y1, x2, y2])

        bubble_boxes = np.array(bubble_boxes) if bubble_boxes else np.array([])
        text_boxes = np.array(text_boxes) if text_boxes else np.array([])
        return bubble_boxes, text_boxes
