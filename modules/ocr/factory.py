import json
import hashlib

from .base import OCREngine
from .microsoft_ocr import MicrosoftOCR
from .google_ocr import GoogleOCR
from .gpt_ocr import GPTOCR
from .rapid_ocr import RapidOCREngine
from .manga_ocr.engine import MangaOCREngine
from .pororo.engine import PororoOCREngine
from .gemini_ocr import GeminiOCR
from ..utils.device import resolve_device

class OCRFactory:
    """Factory for creating appropriate OCR engines based on settings."""
    
    _engines = {}  # Cache of created engines

    LLM_ENGINE_IDENTIFIERS = {
        "GPT": GPTOCR,
        "Gemini": GeminiOCR,
    }
    
    @classmethod
    def create_engine(cls, settings, source_lang_english: str, ocr_model: str) -> OCREngine:
        """
        Create or retrieve an appropriate OCR engine based on settings.
        
        Args:
            settings: Settings object with OCR configuration
            source_lang_english: Source language in English
            ocr_model: OCR model to use
            
        Returns:
            Appropriate OCR engine instance
        """
        # Create a cache key based on model and language
        cache_key = cls._create_cache_key(ocr_model, source_lang_english, settings)
        
        # Return cached engine if available
        if cache_key in cls._engines:
            return cls._engines[cache_key]
        
        # Create engine based on model or language
        engine = cls._create_new_engine(settings, source_lang_english, ocr_model)
        cls._engines[cache_key] = engine
        return engine
    
    @classmethod
    def _create_cache_key(cls, ocr_key: str,
                        source_lang: str,
                        settings) -> str:
        """
        Build a cache key for all ocr engines.

        - Always includes per-ocr credentials (if available),
          so changing any API key, URL, region, etc. triggers a new engine.
        - For LLM engines, also includes all LLM-specific settings
          (temperature, top_p, context, etc.).
        - The cache key is a hash of these dynamic values, combined with
          the ocr key and source language.
        - If no dynamic values are found, falls back to a simple key
          based on ocr and source language.
        """
        base = f"{ocr_key}_{source_lang}"

        # Gather any dynamic bits we care about:
        extras = {}

        # Always grab credentials for this service (if any)
        creds = settings.get_credentials(ocr_key)
        if creds:
            extras["credentials"] = creds

        # The LLM OCR engines currently don't use the settings in the LLMs tab
        # so exclude this for now

        # # If it's an LLM, also grab the llm settings
        # is_llm = any(identifier in ocr_key
        #              for identifier in cls.LLM_ENGINE_IDENTIFIERS)
        # if is_llm:
        #     extras["llm"] = settings.get_llm_settings()

        if not extras:
            return base

        # Otherwise, hash the combined extras dict
        extras_json = json.dumps(
            extras,
            sort_keys=True,
            separators=(",", ":"),
            default=str
        )
        digest = hashlib.sha256(extras_json.encode("utf-8")).hexdigest()

        # Append the fingerprint
        return f"{base}_{digest}"
    
    @classmethod
    def _create_new_engine(cls, settings, source_lang_english: str, ocr_model: str) -> OCREngine:
        """Create a new OCR engine instance based on model and language."""
        
        # Model-specific factory functions
        general = {
            'Microsoft OCR': cls._create_microsoft_ocr,
            'Google Cloud Vision': cls._create_google_ocr,
            'GPT-4.1-mini': lambda s: cls._create_gpt_ocr(s, ocr_model),
            'Gemini-2.0-Flash': lambda s: cls._create_gemini_ocr(s, ocr_model),
        }
        
        # Language-specific factory functions (for Default model)
        language_factories = {
            'Japanese': cls._create_manga_ocr,
            'Korean': cls._create_pororo_ocr,
            'Chinese': lambda s: cls._create_rapid_ocr(s, 'ch'),
            'Russian': lambda s: cls._create_rapid_ocr(s, 'ru'),
            'French': lambda s: cls._create_rapid_ocr(s, 'fr'),
            'English': lambda s: cls._create_rapid_ocr(s, 'en'),
            'Spanish': lambda s: cls._create_rapid_ocr(s, 'es'),
            'Italian': lambda s: cls._create_rapid_ocr(s, 'it'),
            'German': lambda s: cls._create_rapid_ocr(s, 'de'),
            'Dutch': lambda s: cls._create_rapid_ocr(s, 'nl'),
        }
        
        # Check if we have a specific model factory
        if ocr_model in general:
            return general[ocr_model](settings)
        
        # For Default, use language-specific engines
        if ocr_model == 'Default' and source_lang_english in language_factories:
            return language_factories[source_lang_english](settings)
        
        return 
    
    @staticmethod
    def _create_microsoft_ocr(settings) -> OCREngine:
        credentials = settings.get_credentials(settings.ui.tr("Microsoft Azure"))
        engine = MicrosoftOCR()
        engine.initialize(
            api_key=credentials['api_key_ocr'],
            endpoint=credentials['endpoint']
        )
        return engine
    
    @staticmethod
    def _create_google_ocr(settings) -> OCREngine:
        credentials = settings.get_credentials(settings.ui.tr("Google Cloud"))
        engine = GoogleOCR()
        engine.initialize(api_key=credentials['api_key'])
        return engine
    
    @staticmethod
    def _create_gpt_ocr(settings, model) -> OCREngine:
        credentials = settings.get_credentials(settings.ui.tr("Open AI GPT"))
        api_key = credentials.get('api_key', '')
        engine = GPTOCR()
        engine.initialize(api_key=api_key, model=model)
        return engine
    
    @staticmethod
    def _create_manga_ocr(settings) -> OCREngine:
        device = resolve_device(settings.is_gpu_enabled())
        engine = MangaOCREngine()
        engine.initialize(device=device)
        return engine
    
    @staticmethod
    def _create_pororo_ocr(settings) -> OCREngine:
        engine = PororoOCREngine()
        engine.initialize()
        return engine
    
    @staticmethod
    def _create_rapid_ocr(settings, lang: str) -> OCREngine:
        engine = RapidOCREngine()
        engine.initialize(lang=lang, use_gpu=settings.is_gpu_enabled())
        return engine
    
    @staticmethod
    def _create_gemini_ocr(settings, model) -> OCREngine:
        engine = GeminiOCR()
        engine.initialize(settings, model)
        return engine