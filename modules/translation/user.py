import requests
import base64
import numpy as np
import logging
import imkit as imk
import time
from typing import Any, List, Optional

from .base import TranslationEngine
from ..utils.textblock import TextBlock 

from app.account.auth.auth_client import AuthClient
from app.account.auth.token_storage import get_token
from app.ui.settings.settings_page import SettingsPage
from app.account.config import WEB_API_TRANSLATE_URL
from ..utils.exceptions import InsufficientCreditsException


logger = logging.getLogger(__name__)


class UserTranslator(TranslationEngine):
    """
    Desktop translation engine that proxies requests to the web API endpoint,
    utilizing the user's account credits and settings configured server-side.
    """

    def __init__(self, api_url: str = WEB_API_TRANSLATE_URL):
        """
        Args:
            api_url: The full URL of the backend translation endpoint.
        """
        self.api_url = api_url
        self.source_lang: str = None
        self.target_lang: str = None
        self.translator_key: str = None 
        self.settings: SettingsPage = None 
        self.is_llm: bool = False
        self.auth_client: AuthClient = None
        self._session = requests.Session()
        self._profile_web_api = False

    def initialize(self, settings: SettingsPage, source_lang: str, target_lang: str, translator_key: str, **kwargs) -> None:
        """
        Initialize the UserTranslator.

        Args:
            settings: The desktop application's settings object.
            source_lang: Source language name.
            target_lang: Target language name.
            translator_key: The translator selected in the UI (e.g., "GPT-4.1").
        """
        self.settings = settings
        self.source_lang = source_lang
        self.target_lang = target_lang
        self.auth_client = settings.auth_client
        self.translator_key = translator_key
        self.is_llm = self._check_is_llm(translator_key)

    def _check_is_llm(self, translator_key: str) -> bool:
        llm_ids = ["GPT", "Claude", "Gemini", "Deepseek"]
        return any(identifier in translator_key for identifier in llm_ids)
    
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

    def translate(self, blk_list: List[TextBlock], image: np.ndarray = None, extra_context: str = "") -> List[TextBlock]:
        """
        Sends the translation request to the web API.

        Args:
            blk_list: List of TextBlock objects (desktop version) to translate.
            image: Image as numpy array (Optional, for LLM context).
            extra_context: Additional context information for translation.

        Returns:
            List of updated TextBlock objects with translations or error messages.
        """
        start_t = time.perf_counter()
        logger.info(f"UserTranslator: Translating via web API ({self.api_url}) for {self.translator_key}")

        # 1. Get Access Token
        access_token = self._get_access_token()
        after_token_t = time.perf_counter()

        # 2. Prepare Request Body (matching web API's TranslationRequest)
        texts_payload = []
        for i, blk in enumerate(blk_list):
            # Use a simple index or the block's own ID if it has one suitable for mapping
            block_id = getattr(blk, 'id', i) # Use existing ID or index
            texts_payload.append({"id": block_id, "text": blk.text})

        # 3. Get LLM Options from Desktop Settings (if applicable)
        llm_options_payload = None
        if self.is_llm and self.settings:
            # Access LLM settings from the desktop settings object
            llm_settings = self.settings.get_llm_settings() # Assuming this method exists
            llm_options_payload = {
                "temperature": llm_settings.get('temperature', 1.0),
                "image_input_enabled": llm_settings.get('image_input_enabled', False)
            }

        # 4. Handle Image Encoding (if applicable and provided)
        image_base64_payload = None
        should_send_image = (
            self.is_llm
            and image is not None
            and llm_options_payload
            and llm_options_payload.get("image_input_enabled")
        )
         
        if should_send_image:
            # Use JPEG for significantly smaller payloads than PNG (faster over the wire).
            buffer = imk.encode_image(image, "jpg")
            image_base64_payload = base64.b64encode(buffer).decode('utf-8')
            logger.debug("UserTranslator: Encoded image for web API request.")
        after_encode_t = time.perf_counter()

        # 5. Construct Full Payload
        request_payload = {
            "translator": self.translator_key,
            "source_language": self.source_lang,
            "target_language": self.target_lang,
            "texts": texts_payload,
        }

        if image_base64_payload is not None:
            request_payload["image_base64"] = image_base64_payload
        if llm_options_payload is not None:
            request_payload["llm_options"] = llm_options_payload
            request_payload["extra_context"] = extra_context

        # 6. Make the HTTP Request
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {access_token}"
        }

        response = self._session.post(
            self.api_url, 
            headers=headers, 
            json=request_payload, 
            timeout=120
        ) 
        after_request_t = time.perf_counter()
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
                    # JSON parsing failed, just raise the original error
                    pass
            # Re-raise the original error if we didn't handle it
            raise e

        # 7. Process Response
        if response.status_code == 200:
            response_data = response.json()
            translations_map = {item['id']: item['translation'] for item in response_data.get('translations', [])}
            credits_info = response_data.get('credits') or response_data.get('credits_remaining')

            logger.info(f"UserTranslator: Received successful response from web API. Credits: {credits_info}")

            # Update TextBlock objects
            for i, blk in enumerate(blk_list):
                block_id = getattr(blk, 'id', i)
                blk.translation = translations_map.get(block_id, "")

            self.update_credits(credits_info)

        if self._profile_web_api:
            total_t = time.perf_counter() - start_t
            server_ms = response.headers.get("X-CT-Server-Duration-Ms")
            logger.info(
                "UserTranslator timings: token=%.3fs encode=%.3fs http=%.3fs total=%.3fs (texts=%d image=%s server_ms=%s)",
                after_token_t - start_t,
                after_encode_t - after_token_t,
                after_request_t - after_encode_t,
                total_t,
                len(blk_list),
                "yes" if should_send_image else "no",
                server_ms,
            )
            print(
                f"UserTranslator timings: token={after_token_t - start_t:.3f}s "
                f"encode={after_encode_t - after_token_t:.3f}s http={after_request_t - after_encode_t:.3f}s "
                f"total={total_t:.3f}s (texts={len(blk_list)} image={'yes' if should_send_image else 'no'} server_ms={server_ms})"
            )

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
                logger.warning(f"UserTranslator: Unexpected credits format: {credits}")
                return

        self.settings._save_user_info_to_settings()
        self.settings._update_account_view()