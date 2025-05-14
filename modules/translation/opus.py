from typing import Any
import os
import transformers

from .base import TraditionalTranslation
from ..utils.pipeline_utils import get_language_code
from ..utils.translator_utils import MODEL_MAP
from ..utils.textblock import TextBlock

# def get_cache_path():
#     cache_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', 'models', 'huggingface'))
#     if not os.path.isdir(cache_dir): os.makedirs(cache_dir)
#     return cache_dir

def get_opus_code(lang):
    code = get_language_code(lang)
    if not code:
        return 'en'
    return code.split('-', 1)[0]

class OpusTranslation(TraditionalTranslation):
    """Translation engine using Opus-MT models through direct REST API calls."""

    def __init__(self):
        super().__init__()
        self.model_name = None
        self.model = None

    def initialize(self, settings: Any, source_lang: str, target_lang: str, **kwargs) -> None:
        super().initialize(settings, source_lang, target_lang, **kwargs)

        self.source_lang_code = get_opus_code(source_lang)
        self.target_lang_code = get_opus_code(target_lang)
        self.model_name = f"Helsinki-NLP/opus-mt-{self.source_lang_code}-{self.target_lang_code}"

    def translate(self, blk_list: list[TextBlock]) -> list[TextBlock]:
        try:
            if not self.model:
                # self.model = transformers.pipeline(task='translation', model=self.model_name, framework='pt', model_kwargs={'cache_dir':get_cache_path()})
                self.model = transformers.pipeline(task='translation', model=self.model_name, framework='pt')

            batch_size = 25  # Adjust based on typical text length
            for i in range(0, len(blk_list), batch_size):
                batch = blk_list[i:i+batch_size]
                data = []
                indices_to_update = []

                for idx, blk in enumerate(batch):
                    text = self.preprocess_text(blk.text, self.source_lang_code)
                    if not text.strip():
                        blk.translation = ""
                        continue

                    data.append(text)
                    indices_to_update.append(i + idx)

                translations = self.model(data)
                for j, translation_result in enumerate(translations):
                    if j < len(indices_to_update):
                        block_idx = indices_to_update[j]
                        if block_idx < len(blk_list) and 'translation_text' in translation_result:
                            blk_list[block_idx].translation = translation_result['translation_text']

        except Exception as e:
            print(f"Opus Translator error: {str(e)}")

        return blk_list