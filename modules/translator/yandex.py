from typing import Any
import requests

from .base import TraditionalTranslation
from ..utils.textblock import TextBlock


class YandexTranslation(TraditionalTranslation):
    """Translation engine using Yandex Translator API."""
    
    def __init__(self):
        """Initialize Yandex translation engine."""
        self.source_lang_code = None
        self.target_lang_code = None
        self.api_key = None
        self.folder_id = None
        
    def initialize(self, settings: Any, source_lang: str, target_lang: str) -> None:
        self.source_lang_code = self.get_language_code(source_lang)
        self.target_lang_code = self.get_language_code(target_lang)

        if self.target_lang_code.lower().startswith('zh'):
            self.target_lang_code = 'zh'

        elif self.target_lang_code == 'pt-br':
            self.target_lang_code = 'pt-BR' 
        
        credentials = settings.get_credentials(settings.ui.tr("Yandex"))
        self.api_key = credentials.get('api_key', '')
        self.folder_id = credentials.get('folder_id', '')
        
    def translate(self, blk_list: list[TextBlock]) -> list[TextBlock]:
        try:
            # Filter out empty texts
            text_map = {}
            for i, blk in enumerate(blk_list):
                # Handle Chinese/Japanese spacing appropriately
                text = blk.text.replace(" ", "") if (
                    'zh' in self.source_lang_code.lower() or 
                    self.source_lang_code.lower() == 'ja'
                ) else blk.text
                
                if text.strip():
                    text_map[i] = text
            
            if text_map:
                texts_to_translate = list(text_map.values())
                
                # Prepare the request to Yandex.Translate API
                url = "https://translate.api.cloud.yandex.net/translate/v2/translate"
                headers = {
                    "Content-Type": "application/json",
                    "Authorization": f"Api-Key {self.api_key}"
                }
                
                # Build request body with REQUIRED folderId
                body = {
                    "texts": texts_to_translate,
                    "targetLanguageCode": self.target_lang_code,
                    "format": "PLAIN_TEXT",
                    "folderId": self.folder_id  # This is REQUIRED for user accounts
                }
                
                # Make the API request
                response = requests.post(url, headers=headers, json=body)
                response.raise_for_status()  # Raise exception for HTTP errors
                
                # Process the response
                result = response.json()
                translations = result.get("translations", [])
                
                # Map translations back to their original text blocks
                indices = list(text_map.keys())
                for i, translation in enumerate(translations):
                    if i < len(indices):
                        idx = indices[i]
                        blk_list[idx].translation = translation.get("text", "")
            
            # Ensure empty text blocks have empty translations
            for blk in blk_list:
                if not hasattr(blk, 'translation') or blk.translation is None:
                    blk.translation = ""
                    
        except Exception as e:
            print(f"Yandex Translator error: {str(e)}")
            # Print more details if available
            if hasattr(e, 'response') and e.response is not None:
                try:
                    print(f"Response content: {e.response.text}")
                except:
                    pass
            
        return blk_list