from .base import TranslationEngine, TextTranslationEngine, LLMTranslationEngine
from .google import GoogleTranslationEngine
from .microsoft import MicrosoftTranslationEngine
from .deepl import DeepLTranslationEngine
from .yandex import YandexTranslationEngine
from .llm.gpt import GPTTranslationEngine
from .llm.claude import ClaudeTranslationEngine
from .llm.gemini import GeminiTranslationEngine
from .llm.deepseek import DeepseekTranslationEngine
from .llm.custom import CustomTranslationEngine


class TranslationEngineFactory:
    """Factory for creating appropriate translation engines based on settings."""
    
    _engines = {}  # Cache of created engines
    
    # Define which translators are text-based vs LLM-based
    NON_LLM_TRANSLATORS = {"Google Translate", "Microsoft Translator", "DeepL", "Yandex"}
    
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
        cache_key = f"{translator_key}_{source_lang}_{target_lang}"
        
        # Return cached engine if available
        if cache_key in cls._engines:
            return cls._engines[cache_key]
        
        # Create appropriate engine based on translator key
        if translator_key in cls.NON_LLM_TRANSLATORS:
            engine = cls._create_text_based_engine(settings, source_lang, target_lang, translator_key)
        else:
            engine = cls._create_llm_based_engine(settings, source_lang, target_lang, translator_key)
        
        # Cache the engine
        cls._engines[cache_key] = engine
        return engine
    
    @classmethod
    def _create_text_based_engine(cls, settings, source_lang: str, target_lang: str, translator_key: str) -> TextTranslationEngine:
        """Create a text-based translation engine."""
        if translator_key == "Google Translate":
            engine = GoogleTranslationEngine()
        elif translator_key == "Microsoft Translator":
            engine = MicrosoftTranslationEngine()
        elif translator_key == "DeepL":
            engine = DeepLTranslationEngine()
        elif translator_key == "Yandex":
            engine = YandexTranslationEngine()
        else:
            # Default to Google Translate if unknown
            engine = GoogleTranslationEngine()
            
        engine.initialize(settings, source_lang, target_lang)
        return engine
    
    @classmethod
    def _create_llm_based_engine(cls, settings, source_lang: str, target_lang: str, translator_key: str) -> LLMTranslationEngine:
        """Create an LLM-based translation engine."""
        if "GPT" in translator_key:
            engine = GPTTranslationEngine()
        elif "Claude" in translator_key:
            engine = ClaudeTranslationEngine()
        elif "Gemini" in translator_key:
            engine = GeminiTranslationEngine()
        elif "Deepseek" in translator_key:
            engine = DeepseekTranslationEngine()
        elif "Custom" in translator_key:
            engine = CustomTranslationEngine()
        else:
            # Default to GPT if unknown
            engine = GPTTranslationEngine()
            
        engine.initialize(settings, source_lang, target_lang, model_type=translator_key)
        return engine