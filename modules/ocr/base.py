from abc import ABC, abstractmethod
import numpy as np

from ..utils.textblock import TextBlock


class OCREngine(ABC):
    """
    Abstract base class for all OCR engines.
    Each OCR implementation should inherit from this class and implement the process_image method.
    """
    
    @abstractmethod
    def process_image(self, img: np.ndarray, blk_list: list[TextBlock]) -> list[TextBlock]:
        """
        Process an image with OCR and update text blocks with recognized text.
        
        Args:
            img: Input image as numpy array
            blk_list: List of TextBlock objects to update with OCR text
            
        Returns:
            List of updated TextBlock objects with recognized text
        """
        pass

    @abstractmethod
    def initialize(self, **kwargs) -> None:
        """
        Initialize the OCR engine with necessary parameters.
        
        Args:
            **kwargs: Engine-specific initialization parameters
        """
        pass

    @staticmethod
    def set_source_language(blk_list: list[TextBlock], lang_code: str) -> None:
        """
        Set source language code for all text blocks.
        
        Args:
            blk_list: List of TextBlock objects
            lang_code: Language code to set for source language
        """
        for blk in blk_list:
            blk.source_lang = lang_code