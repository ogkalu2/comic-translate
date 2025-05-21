from abc import ABC, abstractmethod
import numpy as np
import cv2
import base64

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

    @staticmethod
    def encode_image(image: np.ndarray, ext: str = '.jpg') -> str:
        """
        Encode an image as base64 string.
        
        Args:
            image: Image as numpy array
            ext: Image format extension (default is .jpg)
        Returns:
            Base64 encoded image string
        """
        success, img_buffer = cv2.imencode(ext, image)
        if not success:
            raise Exception("Failed to encode image")
        return base64.b64encode(img_buffer).decode('utf-8')