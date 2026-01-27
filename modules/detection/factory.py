from .base import DetectionEngine
from .rtdetr_v2_onnx import RTDetrV2ONNXDetection
from ..utils.device import resolve_device, torch_available


class DetectionEngineFactory:
    """Factory for creating appropriate detection engines based on settings."""
    
    _engines = {}  # Cache of created engines
    
    @classmethod
    def create_engine(
        cls, 
        settings, 
        model_name: str = 'RT-DETR-v2', 
        backend: str = 'onnx'
    ) -> DetectionEngine:
        """
        Create or retrieve an appropriate detection engine.
        
        Args:
            settings: Settings object with detection configuration
            model_name: Name of the detection model to use
            backend: Backend to use ('onnx' or 'torch')
            
        Returns:
            Appropriate detection engine instance
        """
        # build cache key
        device = resolve_device(settings.is_gpu_enabled(), backend)
        cache_key = f"{model_name}_{backend}_{device}"

        # Return cached engine if available
        if cache_key in cls._engines:
            return cls._engines[cache_key]
        
        # Map model names to factory methods
        engine_factories = {
            'RT-DETR-v2': cls._create_rtdetr_v2,
        }
        
        # Get the appropriate factory method, defaulting to RT-DETR-v2
        factory_method = engine_factories.get(model_name, cls._create_rtdetr_v2)

        # Create and cache the engine
        engine = factory_method(settings, backend)
        cls._engines[cache_key] = engine
        return engine

    @staticmethod
    def _create_rtdetr_v2(settings, backend: str = 'onnx'):
        """Create and initialize RT-DETR-v2 detection engine."""
        device = resolve_device(settings.is_gpu_enabled(), backend)
        
        if backend.lower() == 'torch' and torch_available():
            from .rtdetr_v2 import RTDetrV2Detection
            engine = RTDetrV2Detection(settings)
            engine.initialize(device=device)
        else:
            engine = RTDetrV2ONNXDetection(settings)
            engine.initialize(device=device)
        
        return engine
    