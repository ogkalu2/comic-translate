import json
import hashlib

from .base import TranslationEngine
from .microsoft import MicrosoftTranslation
from .deepl import DeepLTranslation
from .yandex import YandexTranslation
from .llm.gpt import GPTTranslation
from .llm.claude import ClaudeTranslation
from .llm.gemini import GeminiTranslation
from .llm.deepseek import DeepseekTranslation
from .llm.custom import CustomTranslation
from .llm.ollama import OllamaTranslation
from .user import UserTranslator
from app.account.auth.token_storage import get_token


class TranslationFactory:
    """Factory for creating appropriate translation engines based on settings."""
    
    _engines = {}  # Cache of created engines
    
    # Map traditional translation services to their engine classes
    TRADITIONAL_ENGINES = {
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
        "Custom": CustomTranslation,
        "Ollama": OllamaTranslation
    }
    
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
        if isinstance(engine, UserTranslator):
            # UserTranslator needs the translator_key as positional argument
            engine.initialize(settings, source_lang, target_lang, translator_key)
        else:
            # All other engines (LLM-based and traditional) use named parameters
            engine.initialize(settings, source_lang, target_lang, translator_key=translator_key)
        
        # Cache the engine
        cls._engines[cache_key] = engine
        return engine
    
    @classmethod
    def clear_cache(cls):
        """Clear the engine cache to force recreation on next request."""
        cls._engines.clear()
    

    @classmethod
    def _get_engine_class(cls, translator_key: str):
        """Get the appropriate engine class based on translator key."""

        # Never use account-based engines for local models
        local_translators = ['Custom', 'Ollama']
        is_local_translator = translator_key in local_translators or any(
            identifier in translator_key for identifier in ['Custom', 'Ollama']
        )
        
        if is_local_translator:
            # Force use of the local engine, bypassing account check
            for identifier, engine_class in cls.LLM_ENGINE_IDENTIFIERS.items():
                if identifier in translator_key:
                    return engine_class
        
        access_token = get_token("access_token")
        if access_token and not is_local_translator:
            return UserTranslator

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
        Build a cache key for all translation engines.

        - Always includes per-translator credentials (if available),
          so changing any API key, URL, region, etc. triggers a new engine.
        - For LLM engines, also includes all LLM-specific settings
          (temperature, top_p, context, etc.).
        - The cache key is a hash of these dynamic values, combined with
          the translator key and language pair.
        - If no dynamic values are found, falls back to a simple key
          based on translator and language pair.
        """
        base = f"{translator_key}_{source_lang}_{target_lang}"

        # Gather any dynamic bits we care about:
        extras = {}

        # Always grab credentials for this service (if any)
        creds = settings.get_credentials(translator_key)
        if creds:
            extras["credentials"] = creds

        # If it's an LLM, also grab the llm settings
        is_llm = any(identifier in translator_key
                     for identifier in cls.LLM_ENGINE_IDENTIFIERS)
        if is_llm:
            extras["llm"] = settings.get_llm_settings()

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