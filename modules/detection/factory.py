from .base import DetectionEngine
from .rtdetr_v2_onnx import RTDetrV2ONNXDetection
from ..utils.device import resolve_device


class DetectionEngineFactory:
    """Factory for creating appropriate detection engines based on settings."""
    
    _engines = {}  # Cache of created engines
    
    @classmethod
    def create_engine(cls, settings, model_name: str = 'RT-DETR-v2') -> DetectionEngine:
        """
        Create or retrieve an appropriate detection engine.
        
        Args:
            settings: Settings object with detection configuration
            model_name: Name of the detection model to use
            
        Returns:
            Appropriate detection engine instance
        """
        # Create a cache key based on model
        cache_key = f"{model_name}"
        
        # Return cached engine if available
        if cache_key in cls._engines:
            return cls._engines[cache_key]
        
        # Map model names to factory methods
        engine_factories = {
            'RT-DETR-v2': cls._create_rtdetr_v2_onnx,
        }
        
        # Get the appropriate factory method, defaulting to RT-DETR-V2
        factory_method = engine_factories.get(model_name, cls._create_rtdetr_v2_onnx)

        # Create and cache the engine
        engine = factory_method(settings)
        cls._engines[cache_key] = engine
        return engine

    @staticmethod
    def _create_rtdetr_v2_onnx(settings):
        """Create and initialize RT-DETR-V2 ONNX detection engine."""
        engine = RTDetrV2ONNXDetection()
        device = resolve_device(settings.is_gpu_enabled())
        engine.initialize(device=device)
        return engine
    