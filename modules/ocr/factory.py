import json
import hashlib

from modules.utils.device import resolve_device, torch_available
from app.account.auth.token_storage import get_token
from .base import OCREngine
from .microsoft_ocr import MicrosoftOCR
from .google_ocr import GoogleOCR
from .gpt_ocr import GPTOCR
from .ppocr import PPOCRv5Engine
from .manga_ocr.onnx_engine import MangaOCREngineONNX
from .pororo.onnx_engine import PororoOCREngineONNX  
from .gemini_ocr import GeminiOCR
from .user_ocr import UserOCR


class OCRFactory:
    """Factory for creating appropriate OCR engines based on settings."""
    
    _engines = {}  # Cache of created engines

    LLM_ENGINE_IDENTIFIERS = {
        "GPT": GPTOCR,
        "Gemini": GeminiOCR,
    }
    
    @classmethod
    def clear_cache(cls):
        """Clear the engine cache to force recreation on next request."""
        cls._engines.clear()
    
    @classmethod
    def create_engine(
        cls, 
        settings, 
        source_lang_english: str, 
        ocr_model: str, 
        backend: str = 'onnx'
    ) -> OCREngine:
        """
        Create or retrieve an appropriate OCR engine based on settings.
        
        Args:
            settings: Settings object with OCR configuration
            source_lang_english: Source language in English
            ocr_model: OCR model to use
            backend: Backend to use ('onnx' or 'torch')
            
        Returns:
            Appropriate OCR engine instance
        """
        # build cache key
        cache_key = cls._create_cache_key(
            ocr_model, 
            source_lang_english, 
            settings, 
            backend
        )

        # 1) if we already made it, return it
        if cache_key in cls._engines:
            return cls._engines[cache_key]

        # 2) For account holders, ONLY use account-based OCR if the model requires it
        # Never use account-based OCR for 'Default' model (always use local)
        token = get_token("access_token")
        if token and ocr_model != 'Default' and (
            ocr_model in UserOCR.LLM_OCR_KEYS
            or ocr_model in UserOCR.FULL_PAGE_OCR_KEYS
        ):
            engine = UserOCR()
            engine.initialize(settings, source_lang_english, ocr_model)
            cls._engines[cache_key] = engine
            return engine

        # 3) for local models (Default, Microsoft, Gemini when forced local), create local engines
        engine = cls._create_new_engine(settings, source_lang_english, ocr_model, backend)
        cls._engines[cache_key] = engine
        return engine
    
    @classmethod
    def _create_cache_key(
        cls, 
        ocr_key: str,
        source_lang: str,
        settings, 
        backend: str = 'onnx'
    ) -> str:
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
        base = f"{ocr_key}_{source_lang}_{backend}"

        # Gather any dynamic bits we care about:
        extras = {}

        creds = settings.get_credentials(ocr_key)
        device = resolve_device(settings.is_gpu_enabled(), backend)

        if creds:
            extras["credentials"] = creds
        if device:
            extras["device"] = device

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
    def _create_new_engine(
        cls, 
        settings, 
        source_lang_english: str, 
        ocr_model: str, 
        backend: str = 'onnx'
    ) -> OCREngine:
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
            'Japanese': lambda s: cls._create_manga_ocr(s, backend),
            'Korean': lambda s: cls._create_pororo_ocr(s, backend),
            'Chinese': lambda s: cls._create_ppocr(s, 'ch', backend),
            'Russian': lambda s: cls._create_ppocr(s, 'ru', backend),
            'French': lambda s: cls._create_ppocr(s, 'latin', backend),
            'English': lambda s: cls._create_ppocr(s, 'en', backend),
            'Spanish': lambda s: cls._create_ppocr(s, 'latin', backend),
            'Italian': lambda s: cls._create_ppocr(s, 'latin', backend),
            'German': lambda s: cls._create_ppocr(s, 'latin', backend),
            'Dutch': lambda s: cls._create_ppocr(s, 'latin', backend),
        }
        
        # For Default model, ALWAYS use local language-specific engines
        if ocr_model == 'Default':
            if source_lang_english in language_factories:
                return language_factories[source_lang_english](settings)
            # Fallback to PPOCRv5 English for unsupported languages
            return cls._create_ppocr(settings, 'en', backend)
        
        # Check if we have a specific model factory
        if ocr_model in general:
            return general[ocr_model](settings)
        
        # For any other model, fallback to language-specific or PPOCRv5
        if source_lang_english in language_factories:
            return language_factories[source_lang_english](settings)
        
        # Ultimate fallback to PPOCRv5 English
        return cls._create_ppocr(settings, 'en', backend) 
    
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
    def _create_manga_ocr(settings, backend: str = 'onnx') -> OCREngine:
        device = resolve_device(settings.is_gpu_enabled(), backend)
        
        if backend.lower() == 'torch' and torch_available():
            from .manga_ocr.engine import MangaOCREngine
            engine = MangaOCREngine()
            engine.initialize(device=device)
        else:
            engine = MangaOCREngineONNX()
            engine.initialize(device=device)
        
        return engine
    
    @staticmethod
    def _create_pororo_ocr(settings, backend: str = 'onnx') -> OCREngine:
        device = resolve_device(settings.is_gpu_enabled(), backend)
        
        if backend.lower() == 'torch' and torch_available():
            from .pororo.engine import PororoOCREngine
            engine = PororoOCREngine()
            engine.initialize(device=device)
        else:
            engine = PororoOCREngineONNX()
            engine.initialize(device=device)
        
        return engine
    
    @staticmethod
    def _create_ppocr(settings, lang: str, backend: str = 'onnx') -> OCREngine:
        device = resolve_device(settings.is_gpu_enabled(), backend)
        if backend.lower() == 'torch' and torch_available():
            from .ppocr.torch.engine import PPOCRv5TorchEngine
            device = resolve_device(settings.is_gpu_enabled(), 'torch')
            engine = PPOCRv5TorchEngine()
            engine.initialize(lang=lang, device=device)
        else:
            engine = PPOCRv5Engine()
            engine.initialize(lang=lang, device=device)
        
        return engine
    
    @staticmethod
    def _create_gemini_ocr(settings, model) -> OCREngine:
        engine = GeminiOCR()
        engine.initialize(settings, model)
        return engine