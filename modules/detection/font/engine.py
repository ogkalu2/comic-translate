from abc import ABC, abstractmethod
import os
import logging
import numpy as np
from PIL import Image
import onnxruntime as ort
import imkit as imk
from . import config
from modules.utils.device import resolve_device, get_providers
from modules.utils.download import ModelDownloader, ModelID

logger = logging.getLogger(__name__)


def extract_foreground_color(image: np.ndarray) -> list[int] | None:
    """Extract the foreground (text) color from a text bounding box crop.

    Uses spatial analysis: border pixels define the background colour,
    then Otsu thresholding on the colour-distance-from-background map
    cleanly separates text from background.  The median colour of
    the text pixels is returned.

    This avoids the regression-to-the-mean problem that neural
    regressors suffer from, and correctly handles:
      - black text on white bubble
      - white text on dark/coloured bubble
      - coloured text on any background
    """
    if image is None or image.size == 0:
        return None

    h, w = image.shape[:2]
    if h < 6 or w < 6:
        return None

    if len(image.shape) != 3 or image.shape[2] < 3:
        return None

    img = image[:, :, :3]  # drop alpha if present

    # 1. Border sampling — collect a thin ring of pixels around the edge.
    #    These are almost always background in a text bounding box.
    bw = max(2, min(h, w) // 8)
    top    = img[:bw, :]
    bottom = img[-bw:, :]
    left   = img[bw:-bw, :bw]
    right  = img[bw:-bw, -bw:]

    border_pixels = np.concatenate([
        top.reshape(-1, 3),
        bottom.reshape(-1, 3),
        left.reshape(-1, 3),
        right.reshape(-1, 3),
    ], axis=0).astype(np.float64)

    bg = np.median(border_pixels, axis=0)

    # 2. Per-pixel Euclidean distance from the background colour.
    flat = img.reshape(-1, 3).astype(np.float64)
    dist = np.sqrt(np.sum((flat - bg) ** 2, axis=1))

    # 3. Otsu threshold on the distance map to find the natural
    #    boundary between "background-like" and "text-like" pixels.
    dist_u8 = np.clip(dist, 0, 255).astype(np.uint8)
    otsu_thresh, _ = imk.otsu_threshold(dist_u8)
    # Floor: ignore tiny noise even if Otsu picks a very low split.
    threshold = max(float(otsu_thresh), 25.0)

    # 4. Extract text pixels and compute their median colour.
    text_mask = dist > threshold
    n_text = int(np.sum(text_mask))
    if n_text < 5:
        return None

    fg = np.median(flat[text_mask], axis=0).round().astype(int).tolist()
    return snap_extreme_neutrals(fg)


def snap_extreme_neutrals(rgb: list[int]) -> list[int]:
    """Snap achromatic colours to pure black or white.

    Comic text is almost never intentionally grey.  If the detected
    colour is achromatic (low chroma) it is meant to be either black
    or white, so snap to whichever is closer.  Coloured text (high
    chroma) is returned unchanged.
    """
    r, g, b = int(rgb[0]), int(rgb[1]), int(rgb[2])
    luma = 0.299 * r + 0.587 * g + 0.114 * b
    chroma = max(r, g, b) - min(r, g, b)

    # Achromatic → snap to nearest extreme.
    if chroma < 40:
        return [0, 0, 0] if luma < 128 else [255, 255, 255]

    return [r, g, b]


def build_backbone(model_name: str, *, regression_use_tanh: bool):
    try:
        from .model import ResNet18Regressor, ResNet34Regressor, \
            ResNet50Regressor, ResNet101Regressor, DeepFontBaseline
    except ImportError:
        raise ImportError("Torch is not available")
        
    if model_name == "resnet18":
        return ResNet18Regressor(regression_use_tanh=regression_use_tanh)
    if model_name == "resnet34":
        return ResNet34Regressor(regression_use_tanh=regression_use_tanh)
    if model_name == "resnet50":
        return ResNet50Regressor(regression_use_tanh=regression_use_tanh)
    if model_name == "resnet101":
        return ResNet101Regressor(regression_use_tanh=regression_use_tanh)
    if model_name == "deepfont":
        return DeepFontBaseline()
    raise NotImplementedError(model_name)

class FontEngine(ABC):
    """Abstract base class for font detection engines."""
    
    def __init__(self, settings=None):
        self.settings = settings
        self.input_size = 512
        config.INPUT_SIZE = self.input_size
        self.regression_use_tanh = False # Default assumption

    @abstractmethod
    def initialize(self, device=None, **kwargs) -> None:
        pass

    @abstractmethod
    def process(self, image: np.ndarray) -> dict:
        """
        Process an image crop and return font attributes.
        Args:
            image: numpy array (H, W, C) RGB
        Returns:
            dict with keys: angle, direction, text_color, etc.
        """
        pass

    def decode_output(self, output_vec: np.ndarray, original_width: int) -> dict:
        """
        Decode the non-font attributes from the detector output.
        output_vec: numpy array of shape (N,)
        """
        # Convert to torch tensor for easier processing if needed, or just use numpy
        # Using numpy for ONNX compatibility
        
        needed = config.FONT_COUNT + 12
        if output_vec.size < needed:
            return {"available": False}

        # Direction
        direction_logits = output_vec[config.FONT_COUNT : config.FONT_COUNT + 2]
        direction = "vertical" if direction_logits[1] > direction_logits[0] else "horizontal"
        
        # Softmax for direction probs
        exp_logits = np.exp(direction_logits - np.max(direction_logits))
        direction_probs = exp_logits / exp_logits.sum()

        # Regression
        reg = output_vec[config.FONT_COUNT + 2 : config.FONT_COUNT + 12]

        if self.regression_use_tanh:
            reg = (reg + 1.0) * 0.5

        reg = np.clip(reg, 0.0, 1.0)

        def _rgb(start: int):
            return (reg[start : start + 3] * 255.0).round().astype(int).tolist()

        text_color = snap_extreme_neutrals(_rgb(0))
        font_size_px = float(reg[3] * original_width)
        stroke_width_px = float(reg[4] * original_width)
        stroke_color = snap_extreme_neutrals(_rgb(5))

        line_spacing_px = float(reg[8] * original_width)
        line_height = 1.0 + (line_spacing_px / font_size_px) if font_size_px > 0 else 1.2

        angle_deg = float((reg[9] - 0.5) * 180.0)

        return {
            "available": True,
            "direction": direction,
            "direction_probs": direction_probs.tolist(),
            "text_color": text_color,
            "stroke_color": stroke_color,
            "font_size_px": font_size_px,
            "stroke_width_px": stroke_width_px,
            "line_height": line_height,
            "angle": angle_deg, # Renamed from angle_deg to angle for consistency
        }

class TorchFontEngine(FontEngine):
    def initialize(self, device=None, **kwargs) -> None:
        try:
            import torch
            from torchvision import transforms
            from .model import FontDetector
        except ImportError:
            logger.warning("Warning: Torch not available, cannot initialize TorchFontEngine")
            self.detector = None
            return

        self.device = torch.device(device)   
        self.model_name = "resnet50"
        ckpt_path = ModelDownloader.get_file_path(ModelID.FONT_DETECTOR_TORCH, 'font-detector.ckpt')
            
        if not os.path.exists(ckpt_path):
            logger.warning(f"Warning: Font detection checkpoint not found at {ckpt_path}")
            self.detector = None
            return

        # Build model
        model = build_backbone(self.model_name, regression_use_tanh=self.regression_use_tanh)
        
        self.detector = FontDetector(
            model=model,
            lambda_font=1,
            lambda_direction=1,
            lambda_regression=1,
            font_classification_only=False,
            lr=1,
            betas=(1, 1),
            num_warmup_iters=1,
            num_iters=1e9,
            num_epochs=1e9,
        )

        try:
            ckpt_obj = torch.load(ckpt_path, map_location=self.device, weights_only=False)
            state = ckpt_obj["state_dict"] if "state_dict" in ckpt_obj else ckpt_obj
            
            fixed_state = {}
            for k, v in state.items():
                parts = [p for p in k.split(".") if p != "_orig_mod"]
                fixed_state[".".join(parts)] = v
            
            self.detector.load_state_dict(fixed_state, strict=True)
            self.detector = self.detector.to(self.device)
            self.detector.eval()
            
            self.transform = transforms.Compose([
                transforms.Resize((self.input_size, self.input_size)),
                transforms.ToTensor(),
            ])
            
        except Exception as e:
            logger.error(f"Error loading font detector: {e}")
            self.detector = None

    def process(self, image: np.ndarray) -> dict:
        if self.detector is None:
            return {"available": False}

        import torch

        try:
            pil_image = Image.fromarray(image).convert("RGB")
            original_width = pil_image.width
            
            x = self.transform(pil_image).unsqueeze(0).to(self.device)
            
            with torch.no_grad():
                out = self.detector(x)[0].float().cpu().numpy()
                
            result = self.decode_output(out, original_width)

            # Override model's regressed colour with CV-extracted colour
            cv_color = extract_foreground_color(image)
            if cv_color is not None:
                result["text_color"] = cv_color

            return result
            
        except Exception as e:
            logger.error(f"Error in font detection (Torch): {e}")
            return {"available": False}

class ONNXFontEngine(FontEngine):
    def initialize(self, device=None, **kwargs) -> None:
        model_path = ModelDownloader.get_file_path(ModelID.FONT_DETECTOR_ONNX, 'font-detector.onnx')
        if not os.path.exists(model_path):
            logger.warning(f"Warning: Font detection ONNX model not found at {model_path}")
            self.session = None
            return

        try:
            providers = get_providers(device)            
            self.session = ort.InferenceSession(model_path, providers=providers)
            self.input_name = self.session.get_inputs()[0].name
        except Exception as e:
            logger.error(f"Error loading ONNX font detector: {e}")
            self.session = None

    def process(self, image: np.ndarray) -> dict:
        if self.session is None:
            return {"available": False}

        try:
            pil_image = Image.fromarray(image).convert("RGB")
            original_width = pil_image.width
            
            # Preprocess
            img = pil_image.resize((self.input_size, self.input_size), Image.BILINEAR)
            img_data = np.array(img).astype(np.float32) / 255.0
            img_data = img_data.transpose(2, 0, 1) # HWC -> CHW
            img_data = np.expand_dims(img_data, axis=0) # Add batch dim
            
            outputs = self.session.run(None, {self.input_name: img_data})
            out = outputs[0][0] # First batch item
            
            result = self.decode_output(out, original_width)

            # Override model's regressed colour with CV-extracted colour
            cv_color = extract_foreground_color(image)
            if cv_color is not None:
                result["text_color"] = cv_color

            return result
            
        except Exception as e:
            logger.error(f"Error in font detection (ONNX): {e}")
            return {"available": False}

class FontEngineFactory:
    _engines = {}

    @classmethod
    def create_engine(cls, settings, backend='onnx') -> FontEngine:
        device = resolve_device(settings.is_gpu_enabled() if settings else True, backend)
        cache_key = f"{backend}_{device}"
        
        if cache_key in cls._engines:
            return cls._engines[cache_key]
            
        if backend == 'onnx':
            engine = ONNXFontEngine(settings)
        else:
            engine = TorchFontEngine(settings)
            
        engine.initialize(device=device)
        cls._engines[cache_key] = engine
        return engine
