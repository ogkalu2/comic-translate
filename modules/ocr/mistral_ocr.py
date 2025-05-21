import numpy as np
import requests

from ..utils.textblock import TextBlock
from .base import OCREngine
from app.ui.settings.settings_page import SettingsPage

class MistralOCR(OCREngine):
    """OCR engine using Mistral OCR specific model via REST API with block processing method."""
    def __init__(self):
        self.api_key = None
        self.model = "mistral-ocr-latest"
        self.api_url = "https://api.mistral.ai/v1/ocr"

    def initialize(self, settings: SettingsPage) -> None:
        """
        Initialize the Mistral OCR with API key.
        Args:
            settings: Settings page containing credentials
        """
        credentials = settings.get_credentials(settings.ui.tr('Mistral AI'))
        self.api_key = credentials.get('api_key', '')

    def process_image(self, img: np.ndarray, blk_list: list[TextBlock]) -> list[TextBlock]:
        """
        Process an image with Mistral-based OCR by processing individual text regions.
        Args:
            img: Input image as numpy array
            blk_list: List of TextBlock objects to update with OCR text

        Returns:
            List of updated TextBlock objects with recognized text
        """
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.api_key}"
        }

        for blk in blk_list:
            if blk.xyxy is None:
                blk.text = ""
                continue

            x1, y1, x2, y2 = blk.xyxy.astype(int)
            # Ensure coordinates are valid and within image bounds
            h, w = img.shape[:2]
            x1, y1 = max(0, x1), max(0, y1)
            x2, y2 = min(w, x2), min(h, y2)

            if x1 >= x2 or y1 >= y2: # Check for non-positive area
                blk.text = ""
                continue
                
            cropped_img = img[y1:y2, x1:x2]

            if cropped_img.size == 0:
                blk.text = ""
                continue

            encoded_img = self.encode_image(cropped_img, ext='.jpg')
            image_url = f"data:image/jpeg;base64,{encoded_img}"

            payload = {
                "model": self.model,
                "document": {
                    "type": "image_url",
                    "image_url": image_url
                }
            }

            try:
                response = requests.post(self.api_url, headers=headers, json=payload, timeout=30)
                
                if not response.ok:
                    error_message = f"Mistral OCR API request failed for block with status {response.status_code}"
                    try:
                        error_detail = response.json()
                        if "detail" in error_detail and isinstance(error_detail["detail"], list) and error_detail["detail"]:
                             error_message += f": {error_detail['detail'][0].get('msg', str(error_detail['detail']))}"
                        elif "detail" in error_detail:
                             error_message += f": {error_detail['detail']}"
                        else:
                             error_message += f" Response: {response.text[:200]}" # Limit long responses
                    except ValueError: # JSONDecodeError
                        error_message += f" Raw Response: {response.text[:200]}"
                    print(error_message)
                    continue

                ocr_result = response.json()
                
                if ocr_result.get("pages") and len(ocr_result["pages"]) > 0:
                    blk.text = ocr_result["pages"][0].get("markdown", "").strip()
                else:
                    blk.text = ""

            except requests.exceptions.Timeout:
                print(f"Mistral OCR API request timed out for a block.")
            except requests.exceptions.RequestException as e:
                print(f"Mistral OCR API request failed for a block: {e}")
            except ValueError: # JSONDecodeError
                print(f"Failed to decode Mistral OCR API JSON response for a block.")
            except Exception as e:
                print(f"An unexpected error occurred during Mistral OCR processing for a block: {e}")
        return blk_list
