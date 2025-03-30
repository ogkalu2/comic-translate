import base64
import cv2
import numpy as np
import requests
from typing import List, Dict, Any

from .base import OCREngine
from ..utils.textblock import TextBlock, adjust_text_line_coordinates

class MistralOCR(OCREngine):
    """OCR engine using Mistral Document API."""
    
    def __init__(self):
        """Initialize Mistral OCR engine."""
        self.api_key = None
        self.expansion_percentage = 0
        self.api_url = "https://api.mistral.ai/v1/document"
        self.prompt = "Riconosci il testo nell'immagine. Scrivi esattamente il testo come appare, NON tradurre."
        
    def initialize(self, api_key: str, prompt: str = None,
                   expansion_percentage: int = 0, **kwargs) -> None:
        """
        Initialize the Mistral OCR with API key and parameters.
        
        Args:
            api_key: Mistral API key
            prompt: Custom prompt to use for OCR (optional)
            expansion_percentage: Percentage to expand text bounding boxes
            **kwargs: Additional parameters (ignored)
        """
        self.api_key = api_key
        if prompt:
            self.prompt = prompt
        self.expansion_percentage = expansion_percentage
        
    @staticmethod
    def verify_api_key(api_key: str) -> dict:
        """
        Verify if the API key is valid by making a simple test request.
        
        Args:
            api_key: Mistral API key to verify
            
        Returns:
            Dictionary with validation result
        """
        try:
            headers = {
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json"
            }
            
            # Test with a simple model list API call (leggero)
            response = requests.get("https://api.mistral.ai/v1/models", headers=headers)
            
            # If key is valid, API will return status code 200
            if response.status_code == 200:
                return {
                    "valid": True,
                    "usage": None  # Non recuperiamo l'usage per semplicità
                }
            else:
                # Key is not valid
                error_msg = "Invalid API key"
                try:
                    error_data = response.json()
                    if "error" in error_data:
                        error_msg = error_data["error"]["message"]
                except:
                    pass
                    
                return {
                    "valid": False,
                    "error": error_msg
                }
        except Exception as e:
            print(f"Error verifying Mistral API key: {str(e)}")
            return {
                "valid": False,
                "error": str(e)
            }

    def process_image(self, img: np.ndarray, blk_list: List[TextBlock]) -> List[TextBlock]:
        """
        Process an image with Mistral Document API by processing individual text regions.
        
        Args:
            img: Input image as numpy array
            blk_list: List of TextBlock objects to update with OCR text
            
        Returns:
            List of updated TextBlock objects with recognized text
        """
        for blk in blk_list:
            try:
                # Get box coordinates
                if blk.bubble_xyxy is not None:
                    x1, y1, x2, y2 = blk.bubble_xyxy
                else:
                    x1, y1, x2, y2 = adjust_text_line_coordinates(
                        blk.xyxy,
                        self.expansion_percentage,
                        self.expansion_percentage,
                        img
                    )
                
                # Check if coordinates are valid
                if x1 < x2 and y1 < y2 and x1 >= 0 and y1 >= 0 and x2 <= img.shape[1] and y2 <= img.shape[0]:
                    # Crop image and encode
                    cropped_img = img[y1:y2, x1:x2]
                    cv2_encoded = cv2.imencode('.png', cropped_img)[1]
                    base64_img = base64.b64encode(cv2_encoded).decode('utf-8')
                    
                    # Get OCR result from Mistral
                    text = self._get_mistral_ocr(base64_img)
                    
                    # Replace newlines with spaces
                    blk.text = text.replace('\n', ' ') if '\n' in text else text
            except Exception as e:
                print(f"Mistral OCR error on block: {str(e)}")
                blk.text = ""
                
        return blk_list
    
    def _get_mistral_ocr(self, base64_image: str) -> str:
        """
        Get OCR result from Mistral Document API.
        
        Args:
            base64_image: Base64 encoded image
            
        Returns:
            OCR result text
        """
        try:
            headers = {
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json"
            }
            
            # Use the Document API endpoint
            data = {
                "images": [f"data:image/png;base64,{base64_image}"],
                "prompt": self.prompt
            }
            
            response = requests.post(self.api_url, headers=headers, json=data)
            response.raise_for_status()  # Raise exception if request failed
            
            result = response.json()
            if 'results' in result and len(result['results']) > 0:
                return result['results'][0]['text']
            else:
                print(f"Unexpected response format from Mistral Document API: {result}")
                return ""
        except Exception as e:
            print(f"Mistral Document API error: {str(e)}")
            return ""
