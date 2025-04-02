import cv2
import numpy as np

from azure.ai.vision.imageanalysis import ImageAnalysisClient
from azure.ai.vision.imageanalysis.models import VisualFeatures
from azure.core.credentials import AzureKeyCredential

from .base import OCREngine
from ..utils.textblock import TextBlock
from ..utils.pipeline_utils import lists_to_blk_list


class MicrosoftOCR(OCREngine):
    """OCR engine using Microsoft Azure Computer Vision API."""
    
    def __init__(self):
        """Initialize Microsoft OCR."""
        self.client = None
        self.api_key = None
        self.endpoint = None
        
    def initialize(self, api_key: str, endpoint: str, **kwargs) -> None:
        """
        Initialize the Microsoft OCR with API key and endpoint.
        
        Args:
            api_key: Microsoft Azure API key
            endpoint: Microsoft Azure endpoint URL
            **kwargs: Additional parameters (ignored)
        """
        self.api_key = api_key
        self.endpoint = endpoint
        self.client = ImageAnalysisClient(
            endpoint=endpoint, credential=AzureKeyCredential(api_key)
        )
        
    def process_image(self, img: np.ndarray, blk_list: list[TextBlock]) -> list[TextBlock]:
        """
        Process an image with Microsoft Azure OCR and update text blocks.
        
        Args:
            img: Input image as numpy array
            blk_list: List of TextBlock objects to update with OCR text
            
        Returns:
            List of updated TextBlock objects with recognized text
        """
        texts_bboxes = []
        texts_string = []
        
        try:
            image_buffer = cv2.imencode('.png', img)[1].tobytes()
            result = self.client.analyze(
                image_data=image_buffer, 
                visual_features=[VisualFeatures.READ]
            )
            
            if result.read and result.read.blocks:
                for line in result.read.blocks[0].lines:
                    vertices = line.bounding_polygon
                    
                    # Ensure all vertices have both 'x' and 'y' coordinates
                    if all('x' in vertex and 'y' in vertex for vertex in vertices):
                        x1 = vertices[0]['x']
                        y1 = vertices[0]['y']
                        x2 = vertices[2]['x']
                        y2 = vertices[2]['y']
                        
                        texts_bboxes.append((x1, y1, x2, y2))
                        texts_string.append(line.text)
        
        except Exception as e:
            print(f"Microsoft OCR error: {str(e)}")
            
        return lists_to_blk_list(blk_list, texts_bboxes, texts_string)