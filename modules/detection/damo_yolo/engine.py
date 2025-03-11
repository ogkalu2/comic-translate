import os
import torch
import numpy as np
from typing import List, Tuple
from pathlib import Path

from ..base import DetectionEngine
from modules.utils.textblock import TextBlock
from modules.detection.utils.slicer import ImageSlicer

from .config.base import parse_config
from .detector import build_local_model
from .base_models.core.ops import RepConv
from .structures.image_list import ImageList
from .utils.demo_utils import transform_img


current_file_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.abspath(os.path.join(current_file_dir, '..', '..', '..'))

class DamoYoloDetection(DetectionEngine):
    """Detection engine using a fine-tuned DAMO-YOLO model."""
    
    def __init__(self):
        self.model = None
        self.config = None
        self.device = 'cpu'
        self.default_infer_size = [640, 640]  
        self.confidence_threshold = 0.3
        self.engine_type = 'torch'  
        self.config_path = os.path.join(current_file_dir, 'config', 'damoyolo_tinynasL35_M.py')
        self.model_path = os.path.join(project_root, 'models/detection/comic-detector-damo-yolo.pth')
        # Flag to control whether to use slicing or native resolution handling for very tall images
        self.use_slicing = True
        
        # Initialize image slicer
        self.image_slicer = ImageSlicer(
            height_to_width_ratio_threshold=3.5,
            target_slice_ratio=2.0,
            overlap_height_ratio=0.2,
            min_slice_height_ratio=0.7
        )
        
    def initialize(self, device: str = 'cpu', confidence_threshold: float = 0.3, 
                  use_slicing: bool = True, **kwargs) -> None:
        """
        Initialize DAMO-YOLO model.
        
        Args:
            device: Device to use for inference ("cpu" or "cuda")
            confidence_threshold: Confidence threshold for detections
            use_slicing: Whether to use image slicing for tall images
            **kwargs: Additional parameters
        """
        
        self.device = device
        self.confidence_threshold = confidence_threshold
        self.use_slicing = use_slicing
        
        # Parse config
        self.config = parse_config(self.config_path)
        
        # Determine engine type from model extension
        suffix = Path(self.model_path).suffix.lower()[1:]
        if suffix == 'onnx':
            self.engine_type = 'onnx'
        elif suffix == 'trt':
            self.engine_type = 'tensorRT'
        elif suffix in ['pt', 'pth']:
            self.engine_type = 'torch'
        else:
            self.engine_type = 'torch'  # Default
        
        # Build the model
        self.model = self._build_engine(self.model_path, self.config, self.engine_type)
    
    def _build_engine(self, model_path: str, config, engine_type: str):
        """
        Build the appropriate DAMO-YOLO engine.
        
        Args:
            model_path: Path to the model file
            config: Configuration object
            engine_type: Type of engine to build
            
        Returns:
            Initialized model
        """
        
        print(f'Damo-Yolo Inference with {engine_type} engine!')
        
        if engine_type == 'torch':
            model = build_local_model(config, self.device)
            ckpt = torch.load(model_path, map_location=self.device)
            model.load_state_dict(ckpt['model'], strict=True)
            for layer in model.modules():
                if isinstance(layer, RepConv):
                    layer.switch_to_deploy()
            model.eval()
            return model
        
        elif engine_type == 'onnx':
            import onnxruntime
            session = onnxruntime.InferenceSession(model_path)
            input_name = session.get_inputs()[0].name
            input_shape = session.get_inputs()[0].shape
            
            out_names = []
            out_shapes = []
            for idx in range(len(session.get_outputs())):
                out_names.append(session.get_outputs()[idx].name)
                out_shapes.append(session.get_outputs()[idx].shape)
            
            self.input_name = input_name
            return session
        
        elif engine_type == 'tensorRT':
            import tensorrt as trt
            from cuda import cuda
            loggert = trt.Logger(trt.Logger.INFO)
            trt.init_libnvinfer_plugins(loggert, '')
            runtime = trt.Runtime(loggert)
            
            with open(model_path, 'rb') as t:
                model = runtime.deserialize_cuda_engine(t.read())
                context = model.create_execution_context()
            
            allocations = []
            inputs = []
            outputs = []
            
            for i in range(context.engine.num_bindings):
                is_input = False
                if context.engine.binding_is_input(i):
                    is_input = True
                name = context.engine.get_binding_name(i)
                dtype = context.engine.get_binding_dtype(i)
                shape = context.engine.get_binding_shape(i)
                if is_input:
                    batch_size = shape[0]
                size = np.dtype(trt.nptype(dtype)).itemsize
                for s in shape:
                    size *= s
                allocation = cuda.cuMemAlloc(size)
                binding = {
                    'index': i,
                    'name': name,
                    'dtype': np.dtype(trt.nptype(dtype)),
                    'shape': list(shape),
                    'allocation': allocation,
                    'size': size
                }
                allocations.append(allocation[1])
                if context.engine.binding_is_input(i):
                    inputs.append(binding)
                else:
                    outputs.append(binding)
            
            trt_out = []
            for output in outputs:
                trt_out.append(np.zeros(output['shape'], output['dtype']))
            
            def predict(batch):  # result gets copied into output
                # transfer input data to device
                cuda.cuMemcpyHtoD(inputs[0]['allocation'][1],
                             np.ascontiguousarray(batch), int(inputs[0]['size']))
                # execute model
                context.execute_v2(allocations)
                # transfer predictions back
                for o in range(len(trt_out)):
                    cuda.cuMemcpyDtoH(trt_out[o], outputs[o]['allocation'][1],
                                 outputs[o]['size'])
                return trt_out
            
            return predict
        
        else:
            raise NotImplementedError(f'{engine_type} is not supported yet! Please use one of [onnx, torch, tensorRT]')
    
    def _pad_image(self, img: torch.Tensor, target_size: list[int, int]) -> ImageList:
        """
        Process image to target size by padding if needed.
        
        Args:
            img: Input tensor image (expected shape: [1, C, H, W])
            target_size: Target size [height, width]
            
        Returns:
            Processed image as an ImageList.
        
        Raises:
            ValueError: If input image shape is invalid or exceeds target size.
        """
        
        # Ensure input has batch size of 1
        n, c, h, w = img.shape
        if n != 1:
            raise ValueError(f"Expected batch size of 1, but got {n}")

        # Ensure image does not exceed the target size
        if h > target_size[0] or w > target_size[1]:
            raise ValueError(f"Image size ({h}, {w}) exceeds target size ({target_size[0]}, {target_size[1]})")

        # Define padded tensor
        padded_shape = [n, c, target_size[0], target_size[1]]
        pad_imgs = torch.zeros(*padded_shape, dtype=img.dtype, device=img.device)
        pad_imgs[:, :c, :h, :w].copy_(img)

        img_sizes = [img.shape[-2:]]
        pad_sizes = [pad_imgs.shape[-2:]]

        return ImageList(pad_imgs, img_sizes, pad_sizes)

    
    def _calculate_infer_size(self, image: np.ndarray) -> List[int]:
        """
        Calculate inference size based on image aspect ratio.
        Ensures dimensions are multiples of 32.
        
        Args:
            image: Input image as numpy array
            
        Returns:
            Inference size as [height, width]
        """
        h, w = image.shape[:2]
        
        # If height > 3.5 * width, use original resolution (adjusted to multiple of 32)
        if h > 3.5 * w:
            # Ensure width and height are multiples of 32
            new_w = ((w + 31) // 32) * 32
            new_h = ((h + 31) // 32) * 32
            return [new_h, new_w]
        else:
            # Otherwise use default square size
            return self.default_infer_size
    
    def preprocess(self, origin_img, infer_size=None):
        """
        Preprocess image for model input.
        
        Args:
            origin_img: Original image as numpy array
            infer_size: Size for inference [height, width], or None to use default
            
        Returns:
            Preprocessed image and original dimensions
        """
        
        # Use provided infer_size or calculate based on image aspect ratio
        if infer_size is None:
            infer_size = self._calculate_infer_size(origin_img)

        img = transform_img(origin_img, 0, (640,), keep_ratio=True,
                            infer_size=infer_size)

        oh, ow, _ = origin_img.shape
        img = self._pad_image(img.tensors, infer_size)
        
        img = img.to(self.device)
        return img, (ow, oh)
    
    def postprocess(self, preds, image, origin_shape=None):
        """
        Postprocess model predictions.
        
        Args:
            preds: Model predictions
            image: Input image
            origin_shape: Original image shape
            
        Returns:
            Bounding boxes, scores, and class indices
        """
        from .utils import postprocess
        
        if self.engine_type == 'torch':
            output = preds
        
        elif self.engine_type == 'onnx':
            scores = torch.Tensor(preds[0])
            bboxes = torch.Tensor(preds[1])
            output = postprocess(scores, bboxes,
                          self.config.model.head.num_classes,
                          self.config.model.head.nms_conf_thre,
                          self.config.model.head.nms_iou_thre,
                          image)
        
        elif self.engine_type == 'tensorRT':
            cls_scores = torch.Tensor(preds[0])
            bbox_preds = torch.Tensor(preds[1])
            output = postprocess(cls_scores, bbox_preds,
                         self.config.model.head.num_classes,
                         self.config.model.head.nms_conf_thre,
                         self.config.model.head.nms_iou_thre, image)
        
        output = output[0].resize(origin_shape)
        bboxes = output.bbox
        scores = output.get_field('scores')
        cls_inds = output.get_field('labels')
        
        return bboxes, scores, cls_inds
    
    def forward(self, origin_image):
        """
        Run inference on an image.
        
        Args:
            origin_image: Original image
            
        Returns:
            Bounding boxes, scores, and class indices
        """
        # Calculate appropriate inference size based on image dimensions
        infer_size = self._calculate_infer_size(origin_image)
        
        # Preprocess with calculated size
        image, origin_shape = self.preprocess(origin_image, infer_size=infer_size)
        
        if self.engine_type == 'torch':
            output = self.model(image)
        
        elif self.engine_type == 'onnx':
            image_np = np.asarray(image.tensors.cpu())
            output = self.model.run(None, {self.input_name: image_np})
        
        elif self.engine_type == 'tensorRT':
            image_np = np.asarray(image.tensors.cpu()).astype(np.float32)
            output = self.model(image_np)
        
        bboxes, scores, cls_inds = self.postprocess(output, image, origin_shape=origin_shape)
        
        return bboxes, scores, cls_inds
    
    def _detect_single_image(self, image: np.ndarray) -> Tuple[np.ndarray, np.ndarray]:
        """
        Detect bounding boxes in a single image without slicing.
        
        Args:
            image: Input image as numpy array (BGR format from OpenCV)
            
        Returns:
            Tuple of (bubble_boxes, text_boxes) as numpy arrays
        """
        try:
            # Run inference with appropriate sizing
            bboxes, scores, cls_inds = self.forward(image)
            
            # Convert to numpy arrays and separate bubble and text boxes
            bubble_boxes = []
            text_boxes = []
            
            # Process results
            for i, (box, score, cls_id) in enumerate(zip(bboxes, scores, cls_inds)):
                if score < self.confidence_threshold:
                    continue
                    
                x1, y1, x2, y2 = map(int, box.tolist())
                cls_value = cls_id.item()
                
                if cls_value == 0:  # Bubble class
                    bubble_boxes.append([x1, y1, x2, y2])
                elif cls_value in [1, 2]:  # Text classes (both text_bubble and text_free)
                    text_boxes.append([x1, y1, x2, y2])
            
            # Convert to numpy arrays
            bubble_boxes = np.array(bubble_boxes) if bubble_boxes else np.array([])
            text_boxes = np.array(text_boxes) if text_boxes else np.array([])
            
            return bubble_boxes, text_boxes
            
        except Exception as e:
            print(f"DAMO-YOLO detection error: {str(e)}")
            import traceback
            traceback.print_exc()
            return np.array([]), np.array([])
    
    def detect(self, image: np.ndarray) -> List[TextBlock]:
        """
        Detect text blocks in an image using DAMO-YOLO.
        For tall webtoons, Can use either slicing or native resolution approach.
        
        Args:
            image: Input image as numpy array (BGR format from OpenCV)
            
        Returns:
            List of TextBlock objects with detected regions
        """
        if self.use_slicing:
            # Use the image slicer to process the image and get raw bounding boxes
            bubble_boxes, text_boxes = self.image_slicer.process_slices_for_detection(
                image, 
                self._detect_single_image
            )
        else:
            # Use native resolution approach without slicing
            bubble_boxes, text_boxes = self._detect_single_image(image)
        
        # Create TextBlock objects from the final boxes
        return self.create_text_blocks(image, text_boxes, bubble_boxes)
            

    
