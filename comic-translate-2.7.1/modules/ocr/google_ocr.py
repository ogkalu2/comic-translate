import json
import numpy as np
import requests

from .base import OCREngine
from ..utils.textblock import TextBlock
from ..utils.textblock import lists_to_blk_list


class GoogleOCR(OCREngine):
    """OCR engine using Google Cloud Vision API."""
    
    def __init__(self):
        self.api_key = None
        
    def initialize(self, api_key: str) -> None:
        """
        Initialize the Google OCR with API key.
        
        Args:
            api_key: Google Cloud API key
        """
        self.api_key = api_key
        
    def process_image(self, img: np.ndarray, blk_list: list[TextBlock]) -> list[TextBlock]:
        texts_bboxes = []
        texts_string = []
        
        encoded_image = self.encode_image(img)
        
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
            
        return lists_to_blk_list(blk_list, texts_bboxes, texts_string)