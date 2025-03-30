import base64
import json
import cv2
import numpy as np
import requests

from .base import OCREngine
from ..utils.textblock import TextBlock
from ..utils.pipeline_utils import lists_to_blk_list


class GoogleOCR(OCREngine):
    """OCR engine using Google Cloud Vision API."""
    
    def __init__(self):
        """Initialize Google OCR."""
        self.api_key = None
        
    def initialize(self, api_key: str, **kwargs) -> None:
        """
        Initialize the Google OCR with API key.
        
        Args:
            api_key: Google Cloud API key
            **kwargs: Additional parameters (ignored)
        """
        self.api_key = api_key
        
    def process_image(self, img: np.ndarray, blk_list: list[TextBlock]) -> list[TextBlock]:
        """
        Process an image with Google Cloud Vision OCR and update text blocks.
        
        Args:
            img: Input image as numpy array
            blk_list: List of TextBlock objects to update with OCR text
            
        Returns:
            List of updated TextBlock objects with recognized text
        """
        texts_bboxes = []
        texts_string = []
        
        try:
            encoded_image = base64.b64encode(cv2.imencode('.png', img)[1].tobytes()).decode('utf-8')
            
            payload = {
                "requests": [{
                    "image": {"content": encoded_image}, 
                    "features": [{"type": "TEXT_DETECTION"}]
                }]
            }
            
            headers = {"Content-Type": "application/json"}
            response = requests.post(
                "https://vision.googleapis.com/v1/images:annotate",
                headers=headers,
                params={"key": self.api_key},
                data=json.dumps(payload),
                timeout=10
            )
            
            response.raise_for_status()
            result = response.json()
            
            if 'responses' in result and result['responses'] and 'textAnnotations' in result['responses'][0]:
                texts = result['responses'][0]['textAnnotations']
                
                # Skip the first element which contains all text
                for text in texts[1:]:
                    vertices = text['boundingPoly']['vertices']
                    
                    if all('x' in vertex and 'y' in vertex for vertex in vertices):
                        x1 = vertices[0]['x']
                        y1 = vertices[0]['y']
                        x2 = vertices[2]['x']
                        y2 = vertices[2]['y']
                        
                        texts_bboxes.append((x1, y1, x2, y2))
                        texts_string.append(text['description'])
                        
        except Exception as e:
            print(f"Google OCR error: {str(e)}")
            
        return lists_to_blk_list(blk_list, texts_bboxes, texts_string)