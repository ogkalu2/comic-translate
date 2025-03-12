from .base import OCREngine
from .microsoft_ocr import MicrosoftOCR
from .google_ocr import GoogleOCR
from .gpt_ocr import GPTOCR
from .paddle_ocr import PaddleOCREngine
from .manga_ocr.engine import MangaOCREngine
from .pororo.engine import PororoOCREngine
from .doctr_ocr import DocTROCR
from .gemini_ocr import GeminiOCR

class OCRFactory:
    """Factory for creating appropriate OCR engines based on settings."""
    
    _engines = {}  # Cache of created engines
    
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
        cache_key = f"{ocr_model}_{source_lang_english}"
        
        # Return cached engine if available
        if cache_key in cls._engines:
            return cls._engines[cache_key]
        
        # Create engine based on model or language
        engine = cls._create_new_engine(settings, source_lang_english, ocr_model)
        cls._engines[cache_key] = engine
        return engine
    
    @classmethod
    def _create_new_engine(cls, settings, source_lang_english: str, ocr_model: str) -> OCREngine:
        """Create a new OCR engine instance based on model and language."""
        
        # Model-specific factory functions
        general = {
            'Microsoft OCR': cls._create_microsoft_ocr,
            'Google Cloud Vision': cls._create_google_ocr,
            'GPT-4o': lambda s: cls._create_gpt_ocr(s, ocr_model),
            'Gemini-2.0-Flash': lambda s: cls._create_gemini_ocr(s, ocr_model)
        }
        
        # Language-specific factory functions (for Default model)
        language_factories = {
            'Japanese': cls._create_manga_ocr,
            'Korean': cls._create_pororo_ocr,
            'Chinese': cls._create_paddle_ocr,
            'Russian': lambda s: cls._create_gpt_ocr(s, 'GPT-4o')
        }
        
        # Check if we have a specific model factory
        if ocr_model in general:
            return general[ocr_model](settings)
        
        # For Default, use language-specific engines
        if ocr_model == 'Default' and source_lang_english in language_factories:
            return language_factories[source_lang_english](settings)
        
        # Fallback to doctr for any other language
        return cls._create_doctr_ocr(settings)
    
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
        device = 'cuda' if settings.is_gpu_enabled() else 'cpu'
        engine = MangaOCREngine()
        engine.initialize(device=device)
        return engine
    
    @staticmethod
    def _create_pororo_ocr(settings) -> OCREngine:
        engine = PororoOCREngine()
        engine.initialize()
        return engine
    
    @staticmethod
    def _create_paddle_ocr(settings) -> OCREngine:
        engine = PaddleOCREngine()
        engine.initialize()
        return engine
    
    @staticmethod
    def _create_doctr_ocr(settings) -> OCREngine:
        device = 'cuda' if settings.is_gpu_enabled() else 'cpu'
        engine = DocTROCR()
        engine.initialize(device=device)
        return engine
    
    @staticmethod
    def _create_gemini_ocr(settings, model) -> OCREngine:
        engine = GeminiOCR()
        engine.initialize(settings, model)
        return engine