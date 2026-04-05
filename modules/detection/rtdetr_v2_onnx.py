import os
import numpy as np
from PIL import Image
import onnxruntime as ort

from modules.utils.device import get_providers
from modules.utils.download import ModelDownloader, ModelID, models_base_dir
from modules.utils.textblock import TextBlock
from modules.detection.utils.slicer import ImageSlicer
from .base import DetectionEngine


class RTDetrV2ONNXDetection(DetectionEngine):
    """RT-DETR-v2 ONNX backend detection engine.
    """

    def __init__(self, settings=None):
        super().__init__(settings)
        self.session = None
        self.device = 'cpu'
        self.confidence_threshold = 0.3
        self.model_dir = os.path.join(models_base_dir, 'detection')

        self.image_slicer = ImageSlicer(
            height_to_width_ratio_threshold=3.5,
            target_slice_ratio=3.0,
            overlap_height_ratio=0.2,
            min_slice_height_ratio=0.7
        )

    def initialize(
        self, 
        device: str = 'cpu', 
        confidence_threshold: float = 0.45, 
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

    def supports_image_batching(self) -> bool:
        return True

    def detect_many(self, images: list[np.ndarray]) -> list[list[TextBlock]]:
        if not images:
            return []

        grouped_slices: list[tuple[int, np.ndarray, int]] = []
        per_image_slice_counts = [0] * len(images)
        for image_index, image in enumerate(images):
            if self.image_slicer.should_slice(image):
                width = image.shape[1]
                slice_height = int(width * self.image_slicer.target_slice_ratio)
                effective_slice_height = int(
                    slice_height * (1 - self.image_slicer.overlap_height_ratio)
                )
                num_slices = self.image_slicer.calculate_slice_params(image)[3]
                per_image_slice_counts[image_index] = num_slices
                for slice_number in range(num_slices):
                    slice_img, start_y, _ = self.image_slicer.get_slice(
                        image,
                        slice_number,
                        effective_slice_height,
                        slice_height,
                    )
                    grouped_slices.append((image_index, slice_img, start_y))
            else:
                per_image_slice_counts[image_index] = 1
                grouped_slices.append((image_index, image, 0))

        batch_results = self._detect_many_single_images(
            [slice_image for _, slice_image, _ in grouped_slices]
        )

        per_image_bubbles: list[list[np.ndarray]] = [[] for _ in images]
        per_image_texts: list[list[np.ndarray]] = [[] for _ in images]

        for (image_index, _slice_image, start_y), (bubble_boxes, text_boxes) in zip(
            grouped_slices,
            batch_results,
        ):
            if isinstance(bubble_boxes, np.ndarray) and bubble_boxes.size > 0:
                per_image_bubbles[image_index].append(
                    self.image_slicer.adjust_box_coordinates(bubble_boxes, start_y)
                )
            if isinstance(text_boxes, np.ndarray) and text_boxes.size > 0:
                per_image_texts[image_index].append(
                    self.image_slicer.adjust_box_coordinates(text_boxes, start_y)
                )

        results: list[list[TextBlock]] = []
        for image_index, (image, bubble_groups, text_groups) in enumerate(
            zip(images, per_image_bubbles, per_image_texts)
        ):
            combined_bubbles = np.vstack(bubble_groups) if bubble_groups else np.array([])
            combined_texts = np.vstack(text_groups) if text_groups else np.array([])

            # Match single-image detect() behavior for regular pages:
            # only run slice-recombination merging when the image was actually sliced.
            if per_image_slice_counts[image_index] > 1:
                if combined_bubbles.size > 0:
                    combined_bubbles, _ = self.image_slicer.merge_overlapping_boxes(
                        combined_bubbles,
                        image_height=image.shape[0],
                    )
                if combined_texts.size > 0:
                    combined_texts, _ = self.image_slicer.merge_overlapping_boxes(
                        combined_texts,
                        image_height=image.shape[0],
                    )

            results.append(self.create_text_blocks(image, combined_texts, combined_bubbles))

        return results

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

    def _detect_many_single_images(
        self,
        images: list[np.ndarray],
    ) -> list[tuple[np.ndarray, np.ndarray]]:
        if not images:
            return []

        batch_size = 1
        if self.settings is not None:
            try:
                batch_size = max(1, int(self.settings.get_batch_settings().get("batch_size", 1)))
            except Exception:
                batch_size = 1

        all_results: list[tuple[np.ndarray, np.ndarray]] = []
        for start in range(0, len(images), batch_size):
            chunk = images[start:start + batch_size]
            image_tensors = []
            orig_sizes = []
            for image in chunk:
                pil_image = Image.fromarray(image)
                im_resized = pil_image.resize((640, 640))
                arr = np.asarray(im_resized, dtype=np.float32) / 255.0
                arr = np.transpose(arr, (2, 0, 1))
                image_tensors.append(arr)
                width, height = pil_image.size
                orig_sizes.append([width, height])

            outputs = self.session.run(
                None,
                {
                    "images": np.stack(image_tensors, axis=0).astype(np.float32),
                    "orig_target_sizes": np.asarray(orig_sizes, dtype=np.int64),
                },
            )

            labels_batch, boxes_batch, scores_batch = outputs[:3]
            if isinstance(labels_batch, np.ndarray) and labels_batch.ndim == 1:
                labels_batch = labels_batch[np.newaxis, ...]
            if isinstance(scores_batch, np.ndarray) and scores_batch.ndim == 1:
                scores_batch = scores_batch[np.newaxis, ...]
            if isinstance(boxes_batch, np.ndarray) and boxes_batch.ndim == 2:
                boxes_batch = boxes_batch[np.newaxis, ...]
            for labels, boxes, scores in zip(labels_batch, boxes_batch, scores_batch):
                bubble_boxes = []
                text_boxes = []
                for label, box, score in zip(labels, boxes, scores):
                    if float(score) < float(self.confidence_threshold):
                        continue
                    x1, y1, x2, y2 = map(int, box)
                    label_id = int(label)
                    if label_id == 0:
                        bubble_boxes.append([x1, y1, x2, y2])
                    elif label_id in [1, 2]:
                        text_boxes.append([x1, y1, x2, y2])
                all_results.append(
                    (
                        np.array(bubble_boxes) if bubble_boxes else np.array([]),
                        np.array(text_boxes) if text_boxes else np.array([]),
                    )
                )

        return all_results
