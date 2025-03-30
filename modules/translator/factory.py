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
from .llm.qwen import QwenTranslation, QwenVLPlus, Qwen25VLTranslation, Qwen25VLPaidTranslation


class TranslationEngineFactory:
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
        "Custom": CustomTranslation,
        "Qwen": QwenTranslation
    }
    
    LLM_MAP = {
        'Qwen2.5 VL 72B Instruct (free)': Qwen25VLTranslation,
        'Qwen2.5 VL 72B Instruct': Qwen25VLPaidTranslation,
        'Qwen-vl-2.5': QwenVLPlus,
        'Qwen-Max': QwenTranslation,
        # Aggiungi qui eventuali altri identificatori LLM
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
        print(f"[DEBUG] Creating translation engine for {translator_key}")
        print(f"[DEBUG] Source language: {source_lang}, Target language: {target_lang}")
        
        # Create a cache key based on translator and language pair
        cache_key = f"{translator_key}_{source_lang}_{target_lang}"
        
        # Return cached engine if available
        if cache_key in cls._engines:
            print(f"[DEBUG] Using cached engine for {cache_key}")
            return cls._engines[cache_key]
        
        # Determine engine class and create engine
        engine_class = cls._get_engine_class(translator_key)
        print(f"[DEBUG] Selected engine class: {engine_class.__name__}")
        engine = engine_class()
        
        # Initialize with appropriate parameters
        if translator_key in cls.TRADITIONAL_ENGINES:
            print(f"[DEBUG] Initializing traditional engine: {translator_key}")
            engine.initialize(settings, source_lang, target_lang)
        else:
            print(f"[DEBUG] Initializing LLM engine: {translator_key}")
            engine.initialize(settings, source_lang, target_lang, model_type=translator_key)
        
        # Cache the engine
        cls._engines[cache_key] = engine
        return engine
    
    @classmethod
    def _get_engine_class(cls, translator_key: str):
        """Get the appropriate engine class based on translator key."""
        print(f"[DEBUG] Looking for engine class for: {translator_key}")
        
        # First check if it's a traditional translation engine (exact match)
        if translator_key in cls.TRADITIONAL_ENGINES:
            print(f"[DEBUG] Found in TRADITIONAL_ENGINES")
            return cls.TRADITIONAL_ENGINES[translator_key]
        
        # Check LLM_MAP for exact match first - this is critical for Qwen models
        if translator_key in cls.LLM_MAP:
            print(f"[DEBUG] Found in LLM_MAP")
            return cls.LLM_MAP[translator_key]
            
        # Only then look for partial matches in LLM engine identifiers
        for identifier, engine_class in cls.LLM_ENGINE_IDENTIFIERS.items():
            if identifier in translator_key:
                print(f"[DEBUG] Found as partial match in LLM_ENGINE_IDENTIFIERS: {identifier}")
                return engine_class
        
        # Default to LLM engine if no match found
        print(f"[DEBUG] No match found, using default: {cls.DEFAULT_LLM_ENGINE.__name__}")
        return cls.DEFAULT_LLM_ENGINE