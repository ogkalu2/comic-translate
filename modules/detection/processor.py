import numpy as np

from ..utils.textblock import TextBlock
from .factory import DetectionEngineFactory


class TextBlockDetector:
    """
    Detector for finding text blocks in images.
    """
    
    def __init__(self, settings_page):
        self.settings = settings_page 
        self.engine = None
        self.detector = 'RT-DETR-V2'  # Default Detector
    
    def initialize(self, detector: str = None) -> None:
        if detector:
            self.detector = detector
            
        if self.settings:
            if not detector:
                self.detector = self.settings.get_tool_selection('detector') or self.detector
            
            # Create appropriate engine
            self.engine = DetectionEngineFactory.create_engine(self.settings, self.detector)
    
    def detect(self, img: np.ndarray) -> list[TextBlock]:
        if self.engine is None:
            self.initialize()
            
        if self.engine is None:
            raise ValueError("Detection engine not initialized")
            
        return self.engine.detect(img)