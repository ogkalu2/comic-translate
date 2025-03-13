from .base import DetectionEngine
from .rtdetr_v2 import RTDetrV2Detection


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
            'RT-DETR-v2': cls._create_rtdetr_v2,
        }
        
        # Get the appropriate factory method, defaulting to RT-DETR-V2
        factory_method = engine_factories.get(model_name, cls._create_rtdetr_v2)
        
        # Create and cache the engine
        engine = factory_method(settings)
        cls._engines[cache_key] = engine
        return engine
    
    @staticmethod
    def _create_rtdetr_v2(settings):
        """Create and initialize RT-DETR-V2 detection engine."""
        engine = RTDetrV2Detection()
        device = 'cuda' if settings.is_gpu_enabled() else 'cpu'
        engine.initialize(device=device)
        return engine
    