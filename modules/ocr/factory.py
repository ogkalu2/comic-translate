from .base import OCREngine
from .microsoft_ocr import MicrosoftOCR
from .google_ocr import GoogleOCR
from .gpt_ocr import GPTOCR
from .paddle_ocr import PaddleOCREngine
from .manga_ocr.engine import MangaOCREngine
from .pororo.engine import PororoOCREngine
from .doctr_ocr import DocTROCREngine
from .qwen_ocr import QwenOCREngine, QwenFullOCREngine, QwenVLPlusOCR, QwenMaxOCR
from .mistral_ocr import MistralOCR
from ..utils.translator_utils import get_llm_client, MODEL_MAP

class OCREngineFactory:
    """Factory for creating appropriate OCR engines based on settings."""
    
    _engines = {}  # Cache of created engines
    
    OCR_ENGINE_MAP = {
        'DefaultOCR': DocTROCREngine,
        'Qwen-Max': QwenVLPlusOCR,
        # Aggiungi qui eventuali altri motori OCR
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
        print(f"Creating OCR engine for model: {ocr_model}")
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
            'GPT-4o': lambda s: cls._create_gpt_ocr(s, MODEL_MAP.get('GPT-4o')),
            'Qwen2.5 VL 72B Instruct (free)': cls._create_qwen_ocr,
            'Qwen2.5 VL 72B Instruct': cls._create_qwen_full_ocr,
            'Qwen-Max': cls._create_qwen_max_ocr,
            'Mistral Document': cls._create_mistral_ocr
        }
        
        # Language-specific factory functions (for Default model)
        language_factories = {
            'Japanese': cls._create_manga_ocr,
            'Korean': cls._create_pororo_ocr,
            'Chinese': cls._create_paddle_ocr,
            'Russian': lambda s: cls._create_gpt_ocr(s,  MODEL_MAP.get('GPT-4o'))
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
        gpt_client = get_llm_client('GPT', credentials['api_key'])
        engine = GPTOCR()
        engine.initialize(client=gpt_client, model=model)
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
    def _create_qwen_ocr(settings) -> OCREngine:
        credentials = settings.get_credentials(settings.ui.tr("Qwen2.5 VL 72B Instruct (free)"))
        engine = QwenOCREngine()
        prompt = settings.get_qwen_ocr_prompt() if hasattr(settings, 'get_qwen_ocr_prompt') else None
        engine.initialize(api_key=credentials['api_key'], prompt=prompt)
        return engine
    
    @staticmethod
    def _create_qwen_full_ocr(settings) -> OCREngine:
        credentials = settings.get_credentials(settings.ui.tr("Qwen2.5 VL 72B Instruct"))
        engine = QwenFullOCREngine()
        prompt = settings.get_qwen_ocr_prompt() if hasattr(settings, 'get_qwen_ocr_prompt') else None
        engine.initialize(api_key=credentials['api_key'], prompt=prompt)
        return engine
    
    @staticmethod
    def _create_qwen_max_ocr(settings) -> OCREngine:
        credentials = settings.get_credentials(settings.ui.tr("Qwen-Max"))
        engine = QwenMaxOCR(settings)
        engine.initialize(api_key=credentials['api_key'])
        return engine
    
    @staticmethod
    def _create_mistral_ocr(settings) -> OCREngine:
        credentials = settings.get_credentials(settings.ui.tr("Mistral"))
        engine = MistralOCR()
        prompt = settings.get_qwen_ocr_prompt() if hasattr(settings, 'get_qwen_ocr_prompt') else None
        engine.initialize(api_key=credentials['api_key'], prompt=prompt)
        return engine
    
    @staticmethod
    def _create_doctr_ocr(settings) -> OCREngine:
        device = 'cuda' if settings.is_gpu_enabled() else 'cpu'
        engine = DocTROCREngine()
        engine.initialize(device=device)
        return engine
