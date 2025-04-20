import json
import hashlib

from .base import TranslationEngine
from .google import GoogleTranslation
from .microsoft import MicrosoftTranslation
from .deepl import DeepLTranslation
from .yandex import YandexTranslation
from .llm.gpt import GPTTranslation
from .llm.claude import ClaudeTranslation
from .llm.gemini import GeminiTranslation
from .llm.deepseek import DeepseekTranslation
from .llm.custom import CustomTranslation


class TranslationFactory:
    """Factory for creating appropriate translation engines based on settings."""
    
    _engines = {}  # Cache of created engines
    
    # Map traditional translation services to their engine classes
    TRADITIONAL_ENGINES = {
        "Google Translate": GoogleTranslation,
        "Microsoft Translator": MicrosoftTranslation,
        "DeepL": DeepLTranslation,
        "Yandex": YandexTranslation
    }
    
    # Map LLM identifiers to their engine classes
    LLM_ENGINE_IDENTIFIERS = {
        "GPT": GPTTranslation,
        "Claude": ClaudeTranslation,
        "Gemini": GeminiTranslation,
        "Deepseek": DeepseekTranslation,
        "Custom": CustomTranslation
    }
    
    # Default engines for fallback
    DEFAULT_TRADITIONAL_ENGINE = GoogleTranslation
    DEFAULT_LLM_ENGINE = GPTTranslation
    
    @classmethod
    def create_engine(cls, settings, source_lang: str, target_lang: str, translator_key: str) -> TranslationEngine:
        """
        Create or retrieve an appropriate translation engine based on settings.
        
        Args:
            settings: Settings object with translation configuration
            source_lang: Source language name
            target_lang: Target language name
            translator_key: Key identifying which translator to use
            
        Returns:
            Appropriate translation engine instance
        """
        # Create a cache key based on translator and language pair
        cache_key = cls._create_cache_key(translator_key, source_lang, target_lang, settings)
        
        # Return cached engine if available
        if cache_key in cls._engines:
            return cls._engines[cache_key]
        
        # Determine engine class and create engine
        engine_class = cls._get_engine_class(translator_key)
        engine = engine_class()
        
        # Initialize with appropriate parameters
        if translator_key in cls.TRADITIONAL_ENGINES:
            engine.initialize(settings, source_lang, target_lang)
        else:
            engine.initialize(settings, source_lang, target_lang, translator_key)
        
        # Cache the engine
        cls._engines[cache_key] = engine
        return engine
    
    @classmethod
    def _get_engine_class(cls, translator_key: str):
        """Get the appropriate engine class based on translator key."""
        # First check if it's a traditional translation engine (exact match)
        if translator_key in cls.TRADITIONAL_ENGINES:
            return cls.TRADITIONAL_ENGINES[translator_key]
        
        # Otherwise look for matching LLM engine (substring match)
        for identifier, engine_class in cls.LLM_ENGINE_IDENTIFIERS.items():
            if identifier in translator_key:
                return engine_class
        
        # Default to LLM engine if no match found
        return cls.DEFAULT_LLM_ENGINE
    
    @classmethod
    def _create_cache_key(cls, translator_key: str,
                        source_lang: str,
                        target_lang: str,
                        settings) -> str:
        """
        Build a cache key for both traditional and LLM engines.
        - If it's an LLM (identifier substring in the key), we JSON-hash
          the full settings dict.
        - Otherwise, just use translator_key + langs.
        """
        base = f"{translator_key}_{source_lang}_{target_lang}"

        # detect LLM by seeing if any identifier substr is in the key
        is_llm = any(identifier in translator_key
                     for identifier in cls.LLM_ENGINE_IDENTIFIERS)

        if not is_llm:
            return base

        # pull your full LLM-settings dict (temp, top_p, etc.)
        llm_cfg = settings.get_llm_settings().copy()

        if "Custom" in translator_key:
            creds = settings.get_credentials("Custom")
            # nest the credentials under their own key so they don't collide
            llm_cfg["custom_credentials"] = creds

        # deterministic JSON
        cfg_json = json.dumps(
            llm_cfg,
            sort_keys=True,
            separators=(",", ":"),
            default=str
        )
        # sha256 fingerprint
        digest = hashlib.sha256(cfg_json.encode("utf-8")).hexdigest()
        return f"{base}_{digest}"