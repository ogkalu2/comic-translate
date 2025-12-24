
from typing import Any
import torch
from transformers import pipeline, AutoTokenizer, AutoModelForSeq2SeqLM, AutoModelForCausalLM
import requests
import psutil
import os
import time
from pathlib import Path

from .base import TraditionalTranslation
from ..utils.textblock import TextBlock


def limiter_ressources(cpu_limit=80, ram_limit_gb=4):
    """Met en pause le programme si les limites de CPU/RAM sont dépassées."""
    try:
        process = psutil.Process(os.getpid())
        ram_used_gb = process.memory_info().rss / (1024 ** 3)
        cpu = process.cpu_percent(interval=0.1)

        if cpu > cpu_limit or ram_used_gb > ram_limit_gb:
            print(f"[WARNING] Limite de ressources atteinte (CPU: {cpu:.1f}%, RAM: {ram_used_gb:.2f} Go). Pause de 2s...")
            time.sleep(2)
    except (psutil.NoSuchProcess, psutil.AccessDenied):
        # Le processus a peut-être déjà été tué
        pass


class LocalTransformersTranslation(TraditionalTranslation):
    def __init__(self):
        self.translator = None
        self.source_lang = None
        self.target_lang = None
        self.model_name = None

    def initialize(self, settings: Any, source_lang: str, target_lang: str) -> None:
        self.source_lang = source_lang
        self.target_lang = target_lang
        model_type = getattr(settings, 'local_model_type', 'Seq2Seq (Traduction)')
        if hasattr(settings, 'local_transformers_model') and settings.local_transformers_model:
            model_name = settings.local_transformers_model
        elif hasattr(settings, 'get_credentials'):
            creds = settings.get_credentials('Custom')
            if creds and 'local_transformers_model' in creds and creds['local_transformers_model']:
                model_name = creds['local_transformers_model']
            else:
                model_name = None
        else:
            model_name = None
        if model_type == 'Ollama':
            self.model_name = None
            self.ollama_url = getattr(settings, 'ollama_url', 'http://localhost:11434')
            self.ollama_model = getattr(settings, 'ollama_model', 'llama2')
            print(f"[DEBUG] Utilisation d'Ollama : url={self.ollama_url}, modèle={self.ollama_model}")
            self.translator = None  # Pas de pipeline HuggingFace
            return
        if not model_name:
            raise ValueError("Aucun chemin de modèle local HuggingFace n'a été fourni dans les paramètres.")
        self.model_name = model_name
        print(f"[DEBUG] Chemin du modèle utilisé pour la traduction locale : {self.model_name}")
        self.device = torch.device('cpu')
        if model_type == 'CausalLM (LLM)':
            self.tokenizer = AutoTokenizer.from_pretrained(self.model_name, local_files_only=True)
            self.model = AutoModelForCausalLM.from_pretrained(self.model_name, local_files_only=True).to(self.device)
            self.translator = pipeline('text-generation', model=self.model, tokenizer=self.tokenizer, device=-1)
        else:  # Seq2Seq (Traduction)
            self.tokenizer = AutoTokenizer.from_pretrained(self.model_name, local_files_only=True)
            self.model = AutoModelForSeq2SeqLM.from_pretrained(self.model_name, local_files_only=True).to(self.device)
            self.translator = pipeline('translation', model=self.model, tokenizer=self.tokenizer, device=-1)

    def _nllb_lang_code(self, lang: str) -> str:
        # Mapping minimal pour NLLB (à étendre selon besoin)
        mapping = {
            'en': 'eng_Latn', 'fr': 'fra_Latn', 'es': 'spa_Latn', 'de': 'deu_Latn',
            'it': 'ita_Latn', 'ja': 'jpn_Jpan', 'ko': 'kor_Hang', 'zh': 'zho_Hans',
            'ru': 'rus_Cyrl', 'nl': 'nld_Latn', 'tr': 'tur_Latn',
        }
        return mapping.get(lang, lang)

    def translate(self, blk_list: list[TextBlock]) -> list[TextBlock]:
        print("[DEBUG] Début de la traduction locale (HuggingFace/LLM/Ollama)")
        src_code = self.get_language_code(self.source_lang)
        tgt_code = self.get_language_code(self.target_lang)
        nllb_src = self._nllb_lang_code(src_code)
        nllb_tgt = self._nllb_lang_code(tgt_code)
        model_type = getattr(self, 'model_type', None)
        if hasattr(self, 'ollama_url') and self.ollama_url:
            # Utilisation d'Ollama
            for i, blk in enumerate(blk_list):
                limiter_ressources()
                prompt = f"Traduire en {self.target_lang} : {blk.text}"
                try:
                    response = requests.post(
                        f"{self.ollama_url}/api/generate",
                        json={"model": self.ollama_model, "prompt": prompt, "stream": False},
                        timeout=30
                    )
                    if response.ok:
                        data = response.json()
                        blk.translation = data.get('response', '[Erreur Ollama: pas de réponse]')
                    else:
                        blk.translation = f"[Erreur Ollama: {response.status_code}]"
                except Exception as e:
                    blk.translation = f"[Erreur Ollama: {e}]"
            return blk_list
        # Sinon, pipeline HuggingFace
        try:
            for i, blk in enumerate(blk_list):
                limiter_ressources()
                text = self.preprocess_text(blk.text, src_code)
                print(f"[DEBUG] Bloc {i} : texte à traduire = {repr(text)}")
                try:
                    process = psutil.Process(os.getpid())
                    ram_before_gb = process.memory_info().rss / (1024 ** 3)
                    print(f"[INFO] RAM avant traduction du bloc {i}: {ram_before_gb:.2f} Go")
                    print(f"[DEBUG] Avant appel pipeline HuggingFace pour bloc {i}")
                    if hasattr(self, 'translator') and self.translator is not None:
                        if model_type == 'CausalLM (LLM)':
                            result = self.translator(text, max_length=256)
                            blk.translation = result[0]['generated_text'] if result and isinstance(result, list) and 'generated_text' in result[0] else str(result)
                        else:
                            result = self.translator(text, src_lang=nllb_src, tgt_lang=nllb_tgt, max_length=256)
                            blk.translation = result[0]['translation_text'] if result and isinstance(result, list) and 'translation_text' in result[0] else str(result)
                    else:
                        blk.translation = '[Erreur: pipeline non initialisé]'
                except Exception as e:
                    blk.translation = f"[Erreur traduction: {e}]"
            return blk_list
        except Exception as e:
            for blk in blk_list:
                blk.translation = f"[Erreur traduction: {e}]"
            return blk_list 