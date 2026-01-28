import numpy as np
import requests

from .base import OCREngine
from ..utils.textblock import TextBlock, adjust_text_line_coordinates
from ..utils.translator_utils import MODEL_MAP
from app.ui.settings.settings_page import SettingsPage


class GeminiOCR(OCREngine):
    """OCR engine using Google Gemini models via REST API with block processing method."""
    
    def __init__(self):
        self.api_key = None
        self.expansion_percentage = 5
        self.model = ''
        self.api_base_url = "https://generativelanguage.googleapis.com/v1beta/models"
        self.max_output_tokens = 5000
        
    def initialize(self, settings: SettingsPage, model: str = 'Gemini-2.0-Flash', 
                   expansion_percentage: int = 5) -> None:
        """
        Initialize the Gemini OCR with API key and parameters.
        
        Args:
            settings: Settings page containing credentials
            model: Gemini model to use for OCR (defaults to Gemini-2.0-Flash)
            expansion_percentage: Percentage to expand text bounding boxes
        """
        self.expansion_percentage = expansion_percentage
        credentials = settings.get_credentials(settings.ui.tr('Google Gemini'))
        self.api_key = credentials.get('api_key', '')
        self.model = MODEL_MAP.get(model)
        
    def process_image(self, img: np.ndarray, blk_list: list[TextBlock]) -> list[TextBlock]:
        """
        Process an image with Gemini-based OCR using block processing approach.
        
        Args:
            img: Input image as numpy array
            blk_list: List of TextBlock objects to update with OCR text
            
        Returns:
            List of updated TextBlock objects with recognized text
        """
        return self._process_by_blocks(img, blk_list)
    
    def _process_by_blocks(self, img: np.ndarray, blk_list: list[TextBlock]) -> list[TextBlock]:
        """
        Process an image by processing individual text regions separately.
        Similar to GPTOCR approach, each text block is cropped and sent individually.
        
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
                encoded_img = self.encode_image(cropped_img)
                
                # Get OCR result from Gemini
                blk.text = self._get_gemini_block_ocr(encoded_img)
                
        return blk_list
    
    def _get_gemini_block_ocr(self, base64_image: str) -> str:
        """
        Get OCR result for a single block from Gemini model.
        
        Args:
            base64_image: Base64 encoded image
            
        Returns:
            OCR result text
        """
        if not self.api_key:
            raise ValueError("API key not initialized. Call initialize() first.")
            
        # Create API endpoint URL
        url = f"{self.api_base_url}/{self.model}:generateContent?key={self.api_key}"
        
        # Setup generation config
        generation_config = {
            "maxOutputTokens": self.max_output_tokens,
        }
        
        # Prepare payload
        prompt = """
        Extract the text in this image exactly as it appears. 
        Only output the raw text with no additional comments or descriptions.
        """
        payload = {
            "contents": [{
                "parts": [
                    {
                        "inline_data": {
                            "mime_type": "image/jpeg",
                            "data": base64_image
                        }
                    },
                    {
                        "text": prompt
                    }
                ]
            }],
            "generationConfig": generation_config,
        }
        
        # Make POST request to Gemini API
        headers = {"Content-Type": "application/json"}
        response = requests.post(
            url,
            headers=headers, 
            json=payload,
            timeout=20
        )
        
        # Handle response
        if response.status_code == 200:
            response_data = response.json()
            
            # Extract generated text
            candidates = response_data.get("candidates", [])
            if not candidates:
                return ""
                
            content = candidates[0].get("content", {})
            parts = content.get("parts", [])
            
            # Concatenate all text parts
            result = ""
            for part in parts:
                if "text" in part:
                    result += part["text"]
            
            # Remove any leading/trailing whitespace
            return result.strip()
        else:
            print(f"API error: {response.status_code} {response.text}")
            return ""
