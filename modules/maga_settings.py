from dataclasses import dataclass
from typing import Dict, List, Optional
import os
import shutil
import json

class HDStrategySettings:
    strategy: str = 'Resize'
    resize_limit: int = 960
    crop_margin: int = 512
    crop_trigger_size: int = 512

class ToolSettings:
    translator: str = 'GPT-4'
    ocr: str = 'Default'
    inpainter: str = 'LaMa'
    use_gpu: bool = False
    hd_strategy: HDStrategySettings = HDStrategySettings()

class LLMSettings:
    extra_context: str = ''
    image_input_enabled: bool = False

class ExportSettings:
    export_raw_text: bool = False
    export_translated_text: bool = False
    export_inpainted_image: bool = False
    save_as: Dict[str, str] = None

    def __post_init__(self):
        if self.save_as is None:
            self.save_as = {
                '.pdf': 'pdf',
                '.epub': 'epub',
                '.cbr': 'cbr',
                '.cbz': 'cbz',
                '.cb7': 'cb7',
                '.cbt': 'cbt'
            }

class CredentialSettings:
    save_keys: bool = False
    credentials: Dict[str, Dict] = None

    def __init__(self):
        if self.credentials is None:
            self.credentials = {}


class Translation:
    def __init__(self):
        self.translations = {
            'en_US': {
                'English': 'English',
                'Dark': 'Dark',
            }
        }
        self.current_locale = 'en_US'

    def tr(self, text: str) -> str:
        if self.current_locale in self.translations:
            return self.translations[self.current_locale].get(text, text)
        return text

class UI:
    def __init__(self, tr):
        self.tr = tr

class PSettings:
    def __init__(self):
        self.language = 'English'
        self.theme = 'Dark'
        self.tools = ToolSettings()
        self.llm = LLMSettings()
        self.export = ExportSettings()
        self.credentials = CredentialSettings()
        self.config_file = 'settings.json'
        self.translation = Translation()
        self.ui = UI(self.tr)

    def get_language(self) -> str:
        return self.language

    def get_theme(self) -> str:
        return self.theme

    def get_tool_selection(self, tool_type: str) -> str:
        return getattr(self.tools, tool_type, '')

    def is_gpu_enabled(self) -> bool:
        return self.tools.use_gpu

    def get_llm_settings(self) -> Dict:
        return {
            'extra_context': self.llm.extra_context,
            'image_input_enabled': self.llm.image_input_enabled
        }

    def get_export_settings(self) -> Dict:
        return {
            'export_raw_text': self.export.export_raw_text,
            'export_translated_text': self.export.export_translated_text,
            'export_inpainted_image': self.export.export_inpainted_image,
            'save_as': self.export.save_as
        }

    def get_credentials(self, service: str = "") -> Dict:
        if service:
            if service == "Microsoft Azure":
                return {
                    'api_key_ocr': "Microsoft Azure_api_key_ocr",
                    'api_key_translator': "Microsoft Azure_api_key_translator",
                    'region_translator': "Microsoft Azure_region",
                    'save_key': True,
                    'endpoint': "Microsoft Azure_endpoint"
                }
            elif service == "Custom":
                return {
                    'api_key': self.credentials.credentials.get(f"{service}_api_key"),
                    'api_url': self.credentials.credentials.get(f"{service}_api_url"),
                    'model': self.credentials.credentials.get(f"{service}_model"),
                    'save_key': True
                }
            elif service == "Yandex":
                return {
                    'api_key': self.credentials.credentials.get(f"{service}_api_key"),
                    'folder_id': self.credentials.credentials.get(f"{service}_folder_id"),
                    'save_key': True
                }
            else:
                return {
                    'api_key': self.credentials.credentials.get(f"{service}_api_key"),
                    'save_key': True
                }
        else:
            return {s: self.get_credentials(s) for s in [self.tr("Custom"), self.tr("Deepseek"), self.tr("Open AI GPT"), self.tr("Microsoft Azure"), self.tr("Google Cloud"),
                                    self.tr("Google Gemini"), self.tr("DeepL"), self.tr("Anthropic Claude"), self.tr("Yandex")]}

    def get_hd_strategy_settings(self) -> Dict:
        return {
            'strategy': self.tools.hd_strategy.strategy,
            'resize_limit': self.tools.hd_strategy.resize_limit,
            'crop_margin': self.tools.hd_strategy.crop_margin,
            'crop_trigger_size': self.tools.hd_strategy.crop_trigger_size
        }

    def get_all_settings(self) -> Dict:
        return {
            'language': self.language,
            'theme': self.theme,
            'tools': {
                'translator': self.tools.translator,
                'ocr': self.tools.ocr,
                'inpainter': self.tools.inpainter,
                'use_gpu': self.tools.use_gpu,
                'hd_strategy': self.get_hd_strategy_settings()
            },
            'llm': self.get_llm_settings(),
            'export': self.get_export_settings(),
            'credentials': self.get_credentials(),
            'save_keys': self.credentials.save_keys
        }

    def save_settings(self, config_file: str = None):
        if config_file:
            self.config_file = config_file
        
        settings = self.get_all_settings()
        with open(self.config_file, 'w', encoding='utf-8') as f:
            json.dump(settings, f, indent=4)

    def load_settings(self, config_file: str = None):
        if config_file:
            self.config_file = config_file
            
        if not os.path.exists(self.config_file):
            return

        with open(self.config_file, 'r', encoding='utf-8') as f:
            settings = json.load(f)

        self.language = settings.get('language', 'English')
        self.theme = settings.get('theme', 'Dark')
        
        tools = settings.get('tools', {})
        self.tools.translator = tools.get('translator', 'GPT-4')
        self.tools.ocr = tools.get('ocr', 'Default')
        self.tools.inpainter = tools.get('inpainter', 'LaMa')
        self.tools.use_gpu = tools.get('use_gpu', False)
        
        hd_strategy = tools.get('hd_strategy', {})
        self.tools.hd_strategy = HDStrategySettings(
            strategy=hd_strategy.get('strategy', 'Resize'),
            resize_limit=hd_strategy.get('resize_limit', 960),
            crop_margin=hd_strategy.get('crop_margin', 512),
            crop_trigger_size=hd_strategy.get('crop_trigger_size', 512)
        )

        llm = settings.get('llm', {})
        self.llm.extra_context = llm.get('extra_context', '')
        self.llm.image_input_enabled = llm.get('image_input_enabled', True)

        export = settings.get('export', {})
        self.export.export_raw_text = export.get('export_raw_text', False)
        self.export.export_translated_text = export.get('export_translated_text', False)
        self.export.export_inpainted_image = export.get('export_inpainted_image', False)
        self.export.save_as = export.get('save_as', self.export.save_as)

        self.credentials.save_keys = settings.get('save_keys', False)
        self.credentials.credentials = settings.get('credentials', {})

    def tr(self, text: str) -> str:
        return self.translation.tr(text)