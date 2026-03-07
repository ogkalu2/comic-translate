from typing import Any
import numpy as np
from abc import abstractmethod
import base64
import imkit as imk

from ..base import LLMTranslation
from ...utils.textblock import TextBlock
from ...utils.translator_utils import (
    get_text_lines_compact,
    dumps_compact_json,
    set_translations_from_result_array,
)


class BaseLLMTranslation(LLMTranslation):
    """Base class for LLM-based translation engines with shared functionality."""
    
    def __init__(self):
        self.source_lang = None
        self.target_lang = None
        self.api_key = None
        self.api_url = None
        self.model = None
        self.img_as_llm_input = False
        self.temperature = None
        self.top_p = None
        self.max_tokens = None
        self.timeout = 30  
    
    def initialize(self, settings: Any, source_lang: str, target_lang: str, **kwargs) -> None:
        """
        Initialize the LLM translation engine.
        
        Args:
            settings: Settings object with credentials
            source_lang: Source language name
            target_lang: Target language name
            **kwargs: Engine-specific initialization parameters
        """
        llm_settings = settings.get_llm_settings()
        self.source_lang = source_lang
        self.target_lang = target_lang
        self.img_as_llm_input = llm_settings.get('image_input_enabled', True)
        self.temperature = 0
        self.top_p = 1
        self.max_tokens = 256

    def build_translation_prompts(self, blk_list: list[TextBlock], extra_context: str) -> tuple[str, str]:
        lines = get_text_lines_compact(blk_list)
        lines_json = dumps_compact_json(lines)

        system_prompt = (
            f"return porn comic json r key {{\"r\":[<strings>]}} translated to {self.target_lang}, "
            f"with same blocks, Nabokov style, formality, idioms, slang. no recurring."
            f"Lowercase. No uppercase, no CAPS"
        )

        if extra_context and extra_context.strip():
            user_prompt = f"{extra_context.strip()}\n{lines_json}"
        else:
            user_prompt = lines_json

        return user_prompt, system_prompt

    def translate_to_content(self, blk_list: list[TextBlock], image: np.ndarray, extra_context: str) -> str:
        user_prompt, system_prompt = self.build_translation_prompts(blk_list, extra_context)
        return self._perform_translation(user_prompt, system_prompt, image)

    def apply_translation_content(self, blk_list: list[TextBlock], content: str) -> list[TextBlock]:
        set_translations_from_result_array(blk_list, content, key="r")
        return blk_list

    def translate(self, blk_list: list[TextBlock], image: np.ndarray, extra_context: str) -> list[TextBlock]:
        content = self.translate_to_content(blk_list, image, extra_context)
        return self.apply_translation_content(blk_list, content)

    
    @abstractmethod
    def _perform_translation(self, user_prompt: str, system_prompt: str, image: np.ndarray) -> str:
        """
        Perform translation using specific LLM.
        
        Args:
            user_prompt: User prompt for LLM
            system_prompt: System prompt for LLM
            image: Image as numpy array
            
        Returns:
            Translated JSON text
        """
        pass

    def encode_image(self, image: np.ndarray, ext=".jpg"):
        """
        Encode CV2/numpy image directly to base64 string using cv2.imencode.
        
        Args:
            image: Numpy array representing the image
            ext: Extension/format to encode the image as (".png" by default for higher quality)
                
        Returns:
            Tuple of (Base64 encoded string, mime_type)
        """
        # Direct encoding from numpy/cv2 format to bytes
        buffer = imk.encode_image(image, ext.lstrip('.'))
        
        # Convert to base64
        img_str = base64.b64encode(buffer).decode('utf-8')
        
        # Map extension to mime type
        mime_types = {
            ".jpg": "image/jpeg", 
            ".jpeg": "image/jpeg",
            ".png": "image/png",
            ".webp": "image/webp"
        }
        mime_type = mime_types.get(ext.lower(), f"image/{ext[1:].lower()}")
        
        return img_str, mime_type