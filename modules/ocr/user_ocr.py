import requests
import keyring
import numpy as np
import logging
from typing import Any, List, Optional, Dict

from .base import OCREngine 
from ..utils.textblock import TextBlock 
from ..utils.textblock import lists_to_blk_list
from ..utils.textblock import adjust_text_line_coordinates

from app.account.auth.auth_client import AuthClient
from app.ui.settings.settings_page import SettingsPage
from app.account.config import KEYRING_SERVICE_NAME, \
    WEB_API_OCR_URL, KEYRING_USERNAME


logger = logging.getLogger(__name__)

class UserOCR(OCREngine):
    """
    Desktop OCR engine that proxies requests to the web API endpoint (/ocr),
    utilizing the user's account credits and server-side OCR engines.
    """

    # Define which OCR keys trigger specific API behaviors
    # These should match the keys used in your desktop UI and the web API factory
    LLM_OCR_KEYS = {"GPT-4.1-mini", "Gemini-2.0-Flash"} # Add other LLM models here
    FULL_PAGE_OCR_KEYS = {"Microsoft OCR", "Google Cloud Vision"}

    def __init__(self, api_url: str = WEB_API_OCR_URL):
        """
        Args:
            api_url: The full URL of the backend OCR endpoint.
        """
        self.api_url = api_url
        self.settings: SettingsPage = None
        self.ocr_key: str = None 
        self.source_lang_english: str = None # Store for potential future use or logging
        self.is_llm_type: bool = False # Flag for block-by-block processing
        self.is_full_page_type: bool = False # Flag for full image processing
        self.auth_client: AuthClient = None

    def initialize(self, settings: SettingsPage, source_lang_english: str = None, ocr_key: str = 'Default', **kwargs) -> None:
        """
        Initialize the UserOCR engine.

        Args:
            settings: The desktop application's settings object.
            source_lang_english: Optional source language hint (in English).
            ocr_key: The OCR key selected in the UI (e.g., "Microsoft OCR").
            **kwargs: Catches potential extra arguments from factory.
        """
        self.settings = settings
        self.ocr_key = ocr_key
        self.source_lang_english = source_lang_english # Store if needed by API
        self.auth_client = settings.auth_client

        # Determine processing strategy based on the key
        self.is_llm_type = self.ocr_key in self.LLM_OCR_KEYS
        self.is_full_page_type = self.ocr_key in self.FULL_PAGE_OCR_KEYS

        if not self.is_llm_type and not self.is_full_page_type:
            # This shouldn't happen if the factory logic is correct, but good practice
            logger.error(f"UserOCR initialized with an unsupported key: {self.ocr_key}. Factory should prevent this.")


    def process_image(self, img: np.ndarray, blk_list: List[TextBlock]) -> List[TextBlock]:
        """
        Sends the OCR request to the web API based on the OCR key type.

        Args:
            img: Input image as numpy array.
            blk_list: List of TextBlock objects (desktop version) to update.

        Returns:
            The updated list of TextBlock objects with OCR text or error messages.
        """
        logger.info(f"UserOCR: Attempting OCR via web API ({self.api_url}) for {self.ocr_key}")

        # Get Access Token
        access_token = self._get_access_token()
        if not access_token:
            logger.error("UserOCR Error: Access token not found. Cannot use web API.")
            return blk_list

        # Determine Strategy and Execute
        if self.is_llm_type:
            logger.debug(f"UserOCR: Using block-by-block strategy for {self.ocr_key}")
            return self._process_blocks_llm(img, blk_list, access_token)
        elif self.is_full_page_type:
            logger.debug(f"UserOCR: Using full-page strategy for {self.ocr_key}")
            return self._process_full_page(img, blk_list, access_token)
        else:
            # Fallback or error if key wasn't categorized during init
            logger.error(f"UserOCR: Unknown processing strategy for key '{self.ocr_key}'. Aborting.")
            return blk_list

    def _get_access_token(self) -> Optional[str]:
        """Safely retrieves the access token from keyring."""
        try:
            if not self.auth_client.validate_token():
                logger.error("Access token invalid and refresh failed.")
                return None
            
            token = keyring.get_password(KEYRING_SERVICE_NAME, KEYRING_USERNAME)
            if not token:
                logger.warning("Access token not found in keyring.")
                return None
            return token
        except Exception as e:
            logger.error(f"Failed to retrieve access token from keyring: {e}")
            return None

    def _get_llm_options(self) -> Optional[Dict[str, Any]]:
        """Extracts LLM options from desktop settings."""
        if not self.settings:
            logger.warning("Settings object not available in UserOCR, cannot get LLM options.")
            return None
        
        # Adapt this based on your actual settings structure
        llm_settings = self.settings.get_llm_settings() # Assuming this method exists
        options = {
            "temperature": llm_settings.get('temperature', None), 
            "max_completion_tokens": llm_settings.get('max_tokens', None), 
            "top_p": llm_settings.get('top_p', None), 
        }
        # Filter out None values if the API prefers missing keys over null values
        return {k: v for k, v in options.items() if v is not None}

    def _process_blocks_llm(self, img: np.ndarray, blk_list: List[TextBlock], token: str) -> List[TextBlock]:
        """Handles OCR for LLM types (GPT, Gemini) by processing block by block."""
        headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
        llm_options = self._get_llm_options() # Get common options once

        for i, blk in enumerate(blk_list):
            # Get coordinates for cropping
            if blk.bubble_xyxy is not None:
                x1, y1, x2, y2 = blk.bubble_xyxy
            elif blk.xyxy is not None:
                # Maybe slightly expand the direct text line coordinates for better context?
                # This expansion percentage could be a setting.
                expansion_percentage = 5 # Example: 5% expansion
                x1, y1, x2, y2 = adjust_text_line_coordinates(
                    blk.xyxy, expansion_percentage, expansion_percentage, img
                )
            else:
                logger.warning(f"Block {i} has no coordinates, skipping API call.")
                continue

            # Ensure coordinates are valid before cropping
            h, w = img.shape[:2]
            x1, y1 = max(0, x1), max(0, y1)
            x2, y2 = min(w, x2), min(h, y2)

            if x1 >= x2 or y1 >= y2:
                logger.warning(f"Block {i} has invalid coordinates after clipping: ({x1},{y1},{x2},{y2}). Skipping.")
                continue

            # Crop and Encode the specific block
            cropped_img = img[y1:y2, x1:x2]
            img_b64 = self.encode_image(cropped_img)
            if not img_b64:
                continue # Skip API call if encoding failed

            # Prepare Payload for this block
            payload = {
                "ocr_name": self.ocr_key,
                "image_base64": img_b64,
                "llm_options": llm_options, 
                "source_language": self.source_lang_english # Optional hint
            }

            response = requests.post(
                self.api_url, 
                headers=headers, 
                json=payload, 
                timeout=60
            ) 
            response.raise_for_status()

            if response.status_code == 200:
                response_data = response.json()
                results = response_data.get('ocr_results', [])
                if results:
                    # LLM API should return one result for the cropped image
                    blk.text = results[0].get('text', '')
                    credits_info = response_data.get('credits') or response_data.get('credits_remaining')
                    self.update_credits(credits_info)

        return blk_list

    def _process_full_page(self, img: np.ndarray, blk_list: List[TextBlock], token: str) -> List[TextBlock]:
        """Handles OCR for full-page types (Google, Microsoft)."""
        headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}

        # Encode the entire image
        img_b64 = self.encode_image(img)
        if not img_b64:
            logger.error("UserOCR: Failed to encode the full image.")
            return blk_list

        # Prepare Payload
        payload = {
            "ocr_name": self.ocr_key,
            "image_base64": img_b64,
            "source_language": self.source_lang_english # Optional hint
            # No llm_options needed for these types usually
        }

        # Single API call for the whole page
        response = requests.post(
            self.api_url, 
            headers=headers, 
            json=payload, 
            timeout=120
        ) 
        response.raise_for_status()

        if response.status_code == 200:
            response_data = response.json()
            api_results = response_data.get('ocr_results', [])

            if not api_results:
                logger.warning("UserOCR: Web API returned successful status but no OCR results.")
                return blk_list

            # Extract text and coordinates from API response
            texts_string = []
            texts_bboxes = [] # List of [x1, y1, x2, y2]
            for item in api_results:
                text = item.get('text')
                coords = item.get('coordinates') # Expecting [x1, y1, x2, y2]
                if text and coords and len(coords) == 4:
                    texts_string.append(text)
                    texts_bboxes.append(coords)
                else:
                    logger.warning(f"Skipping API result item due to missing text or invalid coordinates: {item}")

            if not texts_string:
                logger.warning("UserOCR: No valid text/coordinate pairs extracted from API response.")
                return blk_list

            updated_blk_list = lists_to_blk_list(blk_list, texts_bboxes, texts_string)
            credits_info = response_data.get('credits') or response_data.get('credits_remaining')
            self.update_credits(credits_info)
            return updated_blk_list

        return blk_list 
    
    def update_credits(self, credits: Optional[Any]) -> None:
        if credits is None:
            return
        if isinstance(credits, dict):
            self.settings.user_credits = credits
        else:
            try:
                total = int(credits)
                self.settings.user_credits = {
                    'subscription': None,
                    'one_time': total,
                    'total': total,
                }
            except Exception:
                logger.warning(f"UserOCR: Unexpected credits format: {credits}")
                return

        self.settings._save_user_info_to_settings()
        self.settings._update_account_view()