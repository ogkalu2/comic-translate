import numpy as np
import requests
import json

from .base import OCREngine
from ..utils.textblock import TextBlock, adjust_text_line_coordinates
from ..utils.translator_utils import MODEL_MAP


class GPTOCR(OCREngine):
    """OCR engine using GPT vision capabilities via direct REST API calls."""
    
    def __init__(self):
        self.api_key = None
        self.expansion_percentage = 0
        self.model = None
        self.api_base_url = 'https://api.openai.com/v1/chat/completions'
        self.max_tokens = 5000
        
    def initialize(self, api_key: str, model: str = 'GPT-4.1-mini', 
                  expansion_percentage: int = 0) -> None:
        """
        Initialize the GPT OCR with API key and parameters.
        
        Args:
            api_key: OpenAI API key for authentication
            model: GPT model to use for OCR (defaults to gpt-4o)
            expansion_percentage: Percentage to expand text bounding boxes
        """
        self.api_key = api_key
        self.model = MODEL_MAP.get(model)
        self.expansion_percentage = expansion_percentage
        
    def process_image(self, img: np.ndarray, blk_list: list[TextBlock]) -> list[TextBlock]:
        """
        Process an image with GPT-based OCR by processing individual text regions.
        
        Args:
            img: Input image as numpy array
            blk_list: List of TextBlock objects to update with OCR text
            
        Returns:
            List of updated TextBlock objects with recognized text
        """
        for blk in blk_list:
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
                img_to_gpt = self.encode_image(cropped_img)
                
                # Get OCR result from GPT
                blk.text = self._get_gpt_ocr(img_to_gpt)
                
        return blk_list
    
    def _get_gpt_ocr(self, base64_image: str) -> str:
        """
        Get OCR result from GPT model using direct REST API call.
        
        Args:
            base64_image: Base64 encoded image
            
        Returns:
            OCR result text
        """
        if not self.api_key:
            raise ValueError("API key not initialized. Call initialize() first.")
            
        # Prepare request headers
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.api_key}"
        }
        
        # Prepare request payload
        payload = {
            "model": self.model,
            "messages": [
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": "Write out the text in this image. Do NOT Translate. Do not write anything else"},
                        {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{base64_image}"}}
                    ]
                }
            ],
            "max_completion_tokens": self.max_tokens
        }
        
        # Make POST request to OpenAI API
        response = requests.post(
            self.api_base_url,
            headers=headers,
            data=json.dumps(payload),
            timeout=20
        )
        
        # Parse response
        if response.status_code == 200:
            response_json = response.json()
            text = response_json['choices'][0]['message']['content']
            # Replace newlines with spaces
            return text.replace('\n', ' ') if '\n' in text else text
        else:
            print(f"API error: {response.status_code} {response.text}")
            return ""