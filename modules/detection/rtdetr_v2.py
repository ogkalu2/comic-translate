import os
import torch
import imkit as imk
import numpy as np
from PIL import Image
from transformers import RTDetrV2ForObjectDetection, RTDetrImageProcessor

from .base import DetectionEngine
from ..utils.textblock import TextBlock
from .utils.slicer import ImageSlicer
from ..utils.device import tensors_to_device


current_file_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.abspath(os.path.join(current_file_dir, '..', '..'))

class RTDetrV2Detection(DetectionEngine):
    """Detection engine using a fine-tuned RT-DETR-v2 model from Hugging Face."""
    
    def __init__(self, settings=None):
        super().__init__(settings)
        self.model = None
        self.processor = None
        self.device = 'cpu'
        self.confidence_threshold = 0.3
        self.repo_name = 'ogkalu/comic-text-and-bubble-detector'  
        self.model_dir = os.path.join(project_root, 'models/detection')
        
        # Initialize image slicer with default parameters
        self.image_slicer = ImageSlicer(
            height_to_width_ratio_threshold=3.5,
            target_slice_ratio=3.0,
            overlap_height_ratio=0.2,
            min_slice_height_ratio=0.7
        )
        
    def initialize(self, device: str = 'cpu', 
                  confidence_threshold: float = 0.3, **kwargs) -> None:
        self.device = device
        self.confidence_threshold = confidence_threshold
        
        # Load model and processor
        if self.model is None:
            self.processor = RTDetrImageProcessor.from_pretrained(
                self.repo_name,
                size={"width": 640, "height": 640},
            )
            
            self.model = RTDetrV2ForObjectDetection.from_pretrained(
                self.repo_name, 
            )
            
            # Move model to appropriate device
            self.model = self.model.to(self.device)
    
    def detect(self, image: np.ndarray) -> list[TextBlock]:
        # The slicer does not slice images below the width to height threshold
        bubble_boxes, text_boxes = self.image_slicer.process_slices_for_detection(
            image,
            self._detect_single_image
        )
        return self.create_text_blocks(image, text_boxes, bubble_boxes)
    
    def _detect_single_image(self, image: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
        """
        Performs detection on a single image and returns raw bounding boxes.
        
        Args:
            image: Input image in BGR format (OpenCV)
            
        Returns:
            Tuple of (bubble_boxes, text_boxes) as numpy arrays
        """
        # Convert OpenCV image (BGR) to PIL image (RGB)
        pil_image = Image.fromarray(image)  # image is already in RGB format
        
        # Prepare image for model
        inputs = self.processor(images=pil_image, return_tensors="pt")
        # Move inputs to selected device
        inputs = tensors_to_device(inputs, self.device)

        # Run inference
        with torch.no_grad():
            outputs = self.model(**inputs)

        # Post-process results
        target_sizes = torch.tensor([pil_image.size[::-1]], device=self.device)
        results = self.processor.post_process_object_detection(
            outputs,
            target_sizes=target_sizes,
            threshold=self.confidence_threshold,
        )[0]

        # Create bounding boxes for each class
        bubble_boxes = []
        text_boxes = []
        
        for box, score, label in zip(results['boxes'], results['scores'], results['labels']):
            box = box.tolist()
            x1, y1, x2, y2 = map(int, box)
            
            # Class 0: bubble, Class 1: text_bubble, Class 2: text_free
            if label.item() == 0:  # bubble
                bubble_boxes.append([x1, y1, x2, y2])
            elif label.item() in [1, 2]:  # text_bubble or text_free
                text_boxes.append([x1, y1, x2, y2])
        
        # Convert to numpy arrays
        bubble_boxes = np.array(bubble_boxes) if bubble_boxes else np.array([])
        text_boxes = np.array(text_boxes) if text_boxes else np.array([])
        
        return bubble_boxes, text_boxes
    
