import requests
import numpy as np
import logging
import time
from typing import Any, List, Optional, Dict

from .base import OCREngine 
from ..utils.textblock import TextBlock 
from ..utils.textblock import lists_to_blk_list
from ..utils.textblock import adjust_text_line_coordinates

from app.account.auth.auth_client import AuthClient
from app.account.auth.token_storage import get_token
from app.ui.settings.settings_page import SettingsPage
from app.account.config import WEB_API_OCR_URL
from ..utils.exceptions import InsufficientCreditsException


logger = logging.getLogger(__name__)

class UserOCR(OCREngine):
    """
    Desktop OCR engine that proxies requests to the web API endpoint (/ocr),
    utilizing the user's account credits and server-side OCR engines.
    """
    LLM_OCR_KEYS = {"Gemini-2.0-Flash"} 
    FULL_PAGE_OCR_KEYS = {"Microsoft OCR"}

    def __init__(self, api_url: str = WEB_API_OCR_URL):
        """
        Args:
            api_url: The full URL of the backend OCR endpoint.
        """
        self.api_url = api_url
        self.settings: SettingsPage = None
        self.ocr_key: str = None 
        self.source_lang_english: str = None 
        self.is_llm_type: bool = False # Flag for block-by-block processing
        self.is_full_page_type: bool = False # Flag for full image processing
        self.auth_client: AuthClient = None
        self._session = requests.Session()
        self._profile_web_api = False

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
        start_t = time.perf_counter()
        logger.info(f"UserOCR: Attempting OCR via web API ({self.api_url}) for {self.ocr_key}")

        # Get Access Token
        access_token = self._get_access_token()
        if not access_token:
            logger.error("UserOCR Error: Access token not found. Cannot use web API.")
            return blk_list
        after_token_t = time.perf_counter()

        # Determine Strategy and Execute
        if self.is_llm_type:
            logger.debug(f"UserOCR: Using block-by-block strategy for {self.ocr_key}")
            result = self._process_blocks_llm(img, blk_list, access_token)
            if self._profile_web_api:
                msg = f"UserOCR timings: token={after_token_t - start_t:.3f}s total={time.perf_counter() - start_t:.3f}s (mode=llm)"
                logger.info(msg)
                print(msg)
            return result
        elif self.is_full_page_type:
            logger.debug(f"UserOCR: Using full-page strategy for {self.ocr_key}")
            result = self._process_full_page(img, blk_list, access_token)
            if self._profile_web_api:
                msg = f"UserOCR timings: token={after_token_t - start_t:.3f}s total={time.perf_counter() - start_t:.3f}s (mode=full_page)"
                logger.info(msg)
                print(msg)
            return result
        else:
            # Fallback or error if key wasn't categorized during init
            logger.error(f"UserOCR: Unknown processing strategy for key '{self.ocr_key}'. Aborting.")
            return blk_list

    def _get_access_token(self) -> Optional[str]:
        """Retrieves the access token."""
        try:
            if not self.auth_client.validate_token():
                logger.error("Access token invalid and refresh failed.")
                return None
            
            token = get_token("access_token")
            if not token:
                logger.warning("Access token not found.")
                return None
            return token
        except Exception as e:
            logger.error(f"Failed to retrieve access token: {e}")
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
        }
        # Filter out None values if the API prefers missing keys over null values
        return {k: v for k, v in options.items() if v is not None}

    def _process_blocks_llm(self, img: np.ndarray, blk_list: List[TextBlock], token: str) -> List[TextBlock]:
        """
        Handles OCR for LLM types (GPT, Gemini) by sending a single batch request
        containing the full image and a list of coordinates for each text block.
        """
        start_t = time.perf_counter()
        headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
        llm_options = self._get_llm_options()

        # 1. Prepare Validation & Coordinates
        valid_indices = []
        coordinates = []
        
        h, w = img.shape[:2]

        for i, blk in enumerate(blk_list):
            # Determine coordinates to be used
            if blk.bubble_xyxy is not None:
                x1, y1, x2, y2 = blk.bubble_xyxy
            elif blk.xyxy is not None:
                expansion_percentage = 5 
                x1, y1, x2, y2 = adjust_text_line_coordinates(
                    blk.xyxy, expansion_percentage, expansion_percentage, img
                )
            else:
                logger.warning(f"Block {i} has no coordinates, skipping.")
                continue

            # Validate coordinates against image bounds
            x1, y1 = max(0, int(x1)), max(0, int(y1))
            x2, y2 = min(w, int(x2)), min(h, int(y2))

            if x1 >= x2 or y1 >= y2:
                logger.warning(f"Block {i} has invalid coordinates: ({x1},{y1},{x2},{y2}). Skipping.")
                continue

            valid_indices.append(i)
            coordinates.append([x1, y1, x2, y2])

        if not coordinates:
            logger.info("No valid blocks to process.")
            return blk_list

        # 2. Encode Full Image
        img_b64 = self.encode_image(img)
        if not img_b64:
            logger.error("Failed to encode image for batch processing.")
            return blk_list
        after_encode_t = time.perf_counter()

        # 3. Construct Payload
        payload = {
            "ocr_name": self.ocr_key,
            "image_base64": img_b64,
            "llm_options": llm_options,
            "source_language": self.source_lang_english,
            "coordinates": coordinates  # New field for batch processing
        }

        # 4. Send Single Request
        before_http_t = time.perf_counter()
        response = self._session.post(
            self.api_url,
            headers=headers,
            json=payload,
            timeout=120  
        )
        after_http_t = time.perf_counter()
        try:
            response.raise_for_status()
        except requests.exceptions.HTTPError as e:
            if response.status_code == 402:
                try:
                    error_data = response.json()
                    detail = error_data.get('detail')
                    # detail can be a string or a dict
                    if isinstance(detail, dict):
                        description = detail.get('error_description') or detail.get('message')
                    else:
                        description = str(detail)
                    
                    if description:
                        raise InsufficientCreditsException(description)
                except ValueError:
                    pass
            raise e

        if response.status_code == 200:
            response_data = response.json()
            results = response_data.get('ocr_results', [])

            # 5. Map Results back to Blocks
            # We assume the server returns results in the same order as coordinates
            if len(results) != len(valid_indices):
                logger.warning(f"Mismatch in result count: sent {len(coordinates)}, received {len(results)}.")

            for idx_in_results, result_item in enumerate(results):
                # Safely map back if sizes match or iterate up to min length
                if idx_in_results < len(valid_indices):
                    original_blk_idx = valid_indices[idx_in_results]
                    blk = blk_list[original_blk_idx]
                    blk.text = result_item.get('text', '')

            # Update credits
            credits_info = response_data.get('credits') or response_data.get('credits_remaining')
            self.update_credits(credits_info)

        if self._profile_web_api:
            server_ms = response.headers.get("X-CT-Server-Duration-Ms")
            msg = (
                f"UserOCR LLM timings: encode={after_encode_t - start_t:.3f}s "
                f"http={after_http_t - before_http_t:.3f}s total={time.perf_counter() - start_t:.3f}s "
                f"(blocks={len(coordinates)} server_ms={server_ms})"
            )
            logger.info(msg)
            print(msg)
        return blk_list

    def _process_full_page(self, img: np.ndarray, blk_list: List[TextBlock], token: str) -> List[TextBlock]:
        """Handles OCR for full-page types (Google, Microsoft)."""
        start_t = time.perf_counter()
        headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}

        # Encode the entire image
        img_b64 = self.encode_image(img)
        if not img_b64:
            logger.error("UserOCR: Failed to encode the full image.")
            return blk_list
        after_encode_t = time.perf_counter()

        # Prepare Payload
        payload = {
            "ocr_name": self.ocr_key,
            "image_base64": img_b64,
            "source_language": self.source_lang_english 
        }

        # Single API call for the whole page
        before_http_t = time.perf_counter()
        response = self._session.post(
            self.api_url, 
            headers=headers, 
            json=payload, 
            timeout=120
        ) 
        after_http_t = time.perf_counter()
        try:
            response.raise_for_status()
        except requests.exceptions.HTTPError as e:
            if response.status_code == 402:
                try:
                    error_data = response.json()
                    detail = error_data.get('detail')
                    # detail can be a string or a dict
                    if isinstance(detail, dict):
                        description = detail.get('error_description') or detail.get('message')
                    else:
                        description = str(detail)
                    
                    if description:
                        raise InsufficientCreditsException(description)
                except ValueError:
                    pass
            raise e

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
            if self._profile_web_api:
                server_ms = response.headers.get("X-CT-Server-Duration-Ms")
                logger.info(
                    "UserOCR full-page timings: encode=%.3fs http=%.3fs total=%.3fs (items=%d server_ms=%s)",
                    after_encode_t - start_t,
                    after_http_t - before_http_t,
                    time.perf_counter() - start_t,
                    len(api_results),
                    server_ms,
                )
                print(
                    f"UserOCR full-page timings: encode={after_encode_t - start_t:.3f}s "
                    f"http={after_http_t - before_http_t:.3f}s total={time.perf_counter() - start_t:.3f}s "
                    f"(items={len(api_results)} server_ms={server_ms})"
                )
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