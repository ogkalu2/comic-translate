import base64
import cv2
import numpy as np
from typing import List, Any

from .base import OCREngine
from ..utils.textblock import TextBlock, adjust_text_line_coordinates


class GPTOCR(OCREngine):
    """OCR engine using GPT vision capabilities."""
    
    def __init__(self):
        self.client = None
        self.expansion_percentage = 0
        self.model = 'gpt-4o'  
        
    def initialize(self, client: Any, model: str = 'gpt-4o', 
                  expansion_percentage: int = 0) -> None:
        """
        Initialize the GPT OCR with client and parameters.
        
        Args:
            client: GPT client for API calls
            model: GPT model to use for OCR (defaults to gpt-4o)
            expansion_percentage: Percentage to expand text bounding boxes
        """
        self.client = client
        self.model = model
        self.expansion_percentage = expansion_percentage
        
    def process_image(self, img: np.ndarray, blk_list: List[TextBlock]) -> List[TextBlock]:
        """
        Process an image with GPT-based OCR by processing individual text regions.
        
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
                    cv2_to_gpt = cv2.imencode('.png', cropped_img)[1]
                    cv2_to_gpt = base64.b64encode(cv2_to_gpt).decode('utf-8')
                    
                    # Get OCR result from GPT
                    blk.text = self._get_gpt_ocr(cv2_to_gpt)
            except Exception as e:
                print(f"GPT OCR error on block: {str(e)}")
                blk.text = ""
                
        return blk_list
    
    def _get_gpt_ocr(self, base64_image: str) -> str:
        """
        Get OCR result from GPT model.
        
        Args:
            base64_image: Base64 encoded image
            
        Returns:
            OCR result text
        """
        try:
            response = self.client.chat.completions.create(
                model=self.model,  # Use the model specified during initialization
                messages=[
                    {
                        "role": "user",
                        "content": [
                            {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{base64_image}"}},
                            {"type": "text", "text": "Write out the text in this image. Do NOT Translate. Do not write anything else"}
                        ]
                    }
                ],
                max_tokens=1000,
            )
            text = response.choices[0].message.content
            # Replace newlines with spaces
            return text.replace('\n', ' ') if '\n' in text else text
        except Exception as e:
            print(f"GPT API error: {str(e)}")
            return ""