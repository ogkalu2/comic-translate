import json
import logging
from typing import Any
import numpy as np
from abc import abstractmethod
import base64
import imkit as imk

from ..base import LLMTranslation
from ...utils.textblock import TextBlock
from ...utils.translator_utils import (
    get_text_lines_compact,
    dumps_compact_json,
    has_runaway_single_char_repetition,
    is_high_risk_sound_effect_text,
    sanitize_translation_result_text,
    set_translations_from_result_array,
)

logger = logging.getLogger(__name__)


class BaseLLMTranslation(LLMTranslation):
    """Base class for LLM-based translation engines with shared functionality."""
    
    def __init__(self):
        self.source_lang = None
        self.target_lang = None
        self.api_key = None
        self.api_url = None
        self.model = None
        self.img_as_llm_input = False
        self.temperature = None
        self.top_p = None
        self.max_tokens = None
        self.timeout = 30  
    
    def initialize(self, settings: Any, source_lang: str, target_lang: str, **kwargs) -> None:
        """
        Initialize the LLM translation engine.
        
        Args:
            settings: Settings object with credentials
            source_lang: Source language name
            target_lang: Target language name
            **kwargs: Engine-specific initialization parameters
        """
        llm_settings = settings.get_llm_settings()
        self.source_lang = source_lang
        self.target_lang = target_lang
        self.img_as_llm_input = llm_settings.get('image_input_enabled', True)
        self.temperature = float(llm_settings.get("temperature", 0.1))
        self.top_p = float(llm_settings.get("top_p", 0.95))
        self.max_tokens = int(llm_settings.get("max_tokens", 512))

    def _estimate_request_max_tokens(self, blk_list: list[TextBlock]) -> int:
        try:
            total_chars = sum(len(getattr(blk, "text", "") or "") for blk in blk_list)
        except Exception:
            total_chars = 0

        try:
            max_tokens_cap = int(self.max_tokens)
        except (TypeError, ValueError):
            max_tokens_cap = 512

        estimated = 24 + (total_chars * 2) + (len(blk_list) * 8)
        return max(64, min(max_tokens_cap, estimated))

    def _ensure_no_runaway_repetition(self, blk_list: list[TextBlock]) -> None:
        for index, blk in enumerate(blk_list):
            translation = getattr(blk, "translation", "") or ""
            if has_runaway_single_char_repetition(translation):
                raise ValueError(
                    f"Runaway repeated-character output detected for block {index}: {translation[:80]!r}"
                )

    def _is_high_risk_interjection_block(self, blk: TextBlock) -> bool:
        return is_high_risk_sound_effect_text(getattr(blk, "text", "") or "")

    @staticmethod
    def _merge_usage_snapshots(usage_items: list[dict | None]) -> dict | None:
        totals = {
            "prompt_tokens": 0,
            "completion_tokens": 0,
            "total_tokens": 0,
        }
        has_usage = False
        for usage in usage_items:
            if not isinstance(usage, dict):
                continue
            has_usage = True
            for key in totals:
                try:
                    totals[key] += int(usage.get(key, 0) or 0)
                except Exception:
                    continue
        return totals if has_usage else None

    def _snapshot_usage(self) -> dict | None:
        usage = getattr(self, "last_usage", None)
        if isinstance(usage, dict):
            return dict(usage)
        return None

    def build_translation_prompts(self, blk_list: list[TextBlock], extra_context: str) -> tuple[str, str]:
        lines = get_text_lines_compact(blk_list)
        lines_json = dumps_compact_json(lines)
        natural_language_prompt = self.get_system_prompt(self.source_lang, self.target_lang)

        system_prompt = (
            f"{natural_language_prompt} "
            f"Translate the dialogue using the full page context. "
            f"Return ONLY JSON with this structure: {{\"r\":[<strings>]}}. "
            f"Rules: - keep the same number of strings "
            f"- preserve order "
            f"- each output string corresponds to the same input index "
            f"- use surrounding lines as context for translation "
            f"- output must be valid JSON "
            f"- no additional text "
            f"- translate by communicative intent, not dictionary-first word matching "
            f"- short discourse markers, commands, attention signals, concessions, and fillers must be rendered by their function in context, not by literal lexical meaning "
            f"- preserve tone, emotion, and punctuation where natural in the target language "
            f"- ensure correct agreement and inflection where applicable, including gender, number, case, person, tense, and register "
            f"- do not mirror source syntax when it sounds unnatural in the target language "
            f"- use standard real words of the target language; do not invent pseudo-words or distorted transliterations unless the source is intentionally nonsense "
            f"- for screams, groans, stutters, and elongated sounds, translate to a natural target-language equivalent instead of mechanically copying source letter counts "
            f"- if gender or other morphology is not explicit, choose the most natural context-compatible phrasing, preferably neutral or impersonal wording, rather than a literal guess "
            f"- before answering, silently normalize each line so it reads like something a native speaker would naturally say in the target language "
            f"- never let one character dominate the output"
        )

        if extra_context and extra_context.strip():
            user_prompt = f"{extra_context.strip()}\n{lines_json}"
        else:
            user_prompt = lines_json

        return user_prompt, system_prompt

    def build_interjection_prompts(self, blk_list: list[TextBlock], extra_context: str) -> tuple[str, str]:
        lines = get_text_lines_compact(blk_list)
        lines_json = dumps_compact_json(lines)
        natural_language_prompt = self.get_system_prompt(self.source_lang, self.target_lang)

        system_prompt = (
            f"{natural_language_prompt} "
            f"Translate the single dialogue line below. "
            f"This line is likely a scream, groan, stutter, elongated sound, panic shout, or other emotional interjection. "
            f"Return ONLY JSON with this structure: {{\"r\":[<string>]}}. "
            f"Rules: - output must be valid JSON "
            f"- no extra text "
            f"- produce a short natural equivalent in the target language "
            f"- preserve communicative force and emotion, not the exact letter pattern "
            f"- never mechanically copy long repeated letters "
            f"- prefer a concise native-sounding exclamation over a literal or broken form "
            f"- if no good translation exists, keep a concise stylized equivalent rather than a long repeated sequence "
            f"- never output more than 4 identical characters in a row"
        )

        if extra_context and extra_context.strip():
            user_prompt = f"{extra_context.strip()}\n{lines_json}"
        else:
            user_prompt = lines_json

        return user_prompt, system_prompt

    def _translate_group(
        self,
        blk_list: list[TextBlock],
        image: np.ndarray,
        extra_context: str,
        *,
        interjection_mode: bool = False,
    ) -> dict | None:
        prompt_builder = self.build_interjection_prompts if interjection_mode else self.build_translation_prompts
        user_prompt, system_prompt = prompt_builder(blk_list, extra_context)
        retry_prompt = (
            system_prompt
            + " If any item is uncertain, return an empty string for that item."
            + " Never emit malformed JSON, truncated JSON, or filler character repetition."
            + " Prefer idiomatic native phrasing over literal closeness to source wording."
        )
        if interjection_mode:
            retry_prompt += (
                " Keep the result brief and emotionally natural."
                " Do not preserve long repeated-letter runs from the source."
            )
        else:
            retry_prompt += (
                " For interjections and screams, prefer a short natural equivalent in the target language."
                " Rewrite awkward literal phrasing into fluent target-language speech before returning JSON."
                " Never output more than 6 identical characters in a row."
            )

        last_exc: Exception | None = None
        original_translations = [getattr(blk, "translation", "") for blk in blk_list]
        original_max_tokens = self.max_tokens
        original_temperature = self.temperature
        original_top_p = self.top_p
        estimated_max_tokens = self._estimate_request_max_tokens(blk_list)
        self.max_tokens = min(estimated_max_tokens, 64) if interjection_mode else estimated_max_tokens
        if interjection_mode:
            self.temperature = 0.0
            top_p_value = float(self.top_p) if self.top_p is not None else 1.0
            self.top_p = min(top_p_value, 0.85)
        try:
            for attempt_index, prompt in enumerate((system_prompt, retry_prompt), start=1):
                content = self._perform_translation(user_prompt, prompt, image)
                usage_snapshot = self._snapshot_usage()
                try:
                    result = self.apply_translation_content(blk_list, content)
                    self._ensure_no_runaway_repetition(result)
                    return usage_snapshot
                except (json.JSONDecodeError, ValueError) as exc:
                    last_exc = exc
                    for blk, original_translation in zip(blk_list, original_translations):
                        blk.translation = original_translation
                    if attempt_index >= 2:
                        break
                    logger.warning(
                        "LLM translation returned invalid structured output on attempt %d; retrying once with stricter JSON instructions: %s",
                        attempt_index,
                        exc,
                    )
        finally:
            self.max_tokens = original_max_tokens
            self.temperature = original_temperature
            self.top_p = original_top_p

        if interjection_mode and len(blk_list) == 1 and self._is_high_risk_interjection_block(blk_list[0]):
            blk = blk_list[0]
            blk.translation = sanitize_translation_result_text(getattr(blk, "text", "") or "")
            logger.warning(
                "LLM interjection translation fell back to preserved source text after repeated invalid output: %r",
                blk.translation[:80],
            )
            return self._snapshot_usage()

        if last_exc is not None:
            raise last_exc
        return None

    def translate_to_content(self, blk_list: list[TextBlock], image: np.ndarray, extra_context: str) -> str:
        user_prompt, system_prompt = self.build_translation_prompts(blk_list, extra_context)
        return self._perform_translation(user_prompt, system_prompt, image)

    def apply_translation_content(self, blk_list: list[TextBlock], content: str) -> list[TextBlock]:
        set_translations_from_result_array(blk_list, content, key="r")
        return blk_list

    def translate(self, blk_list: list[TextBlock], image: np.ndarray, extra_context: str) -> list[TextBlock]:
        usage_items: list[dict | None] = []
        risky_blocks = [blk for blk in blk_list if self._is_high_risk_interjection_block(blk)]

        if risky_blocks and len(blk_list) > 1:
            normal_blocks = [blk for blk in blk_list if blk not in risky_blocks]
            if normal_blocks:
                usage_items.append(
                    self._translate_group(
                        normal_blocks,
                        image,
                        extra_context,
                        interjection_mode=False,
                    )
                )
            for blk in risky_blocks:
                usage_items.append(
                    self._translate_group(
                        [blk],
                        image,
                        extra_context,
                        interjection_mode=True,
                    )
                )
            self.last_usage = self._merge_usage_snapshots(usage_items)
            return blk_list

        usage = self._translate_group(
            blk_list,
            image,
            extra_context,
            interjection_mode=(len(blk_list) == 1 and bool(risky_blocks)),
        )
        self.last_usage = usage
        return blk_list

    
    @abstractmethod
    def _perform_translation(self, user_prompt: str, system_prompt: str, image: np.ndarray) -> str:
        """
        Perform translation using specific LLM.
        
        Args:
            user_prompt: User prompt for LLM
            system_prompt: System prompt for LLM
            image: Image as numpy array
            
        Returns:
            Translated JSON text
        """
        pass

    def encode_image(self, image: np.ndarray, ext=".jpg"):
        """
        Encode CV2/numpy image directly to base64 string using cv2.imencode.
        
        Args:
            image: Numpy array representing the image
            ext: Extension/format to encode the image as (".png" by default for higher quality)
                
        Returns:
            Tuple of (Base64 encoded string, mime_type)
        """
        # Direct encoding from numpy/cv2 format to bytes
        buffer = imk.encode_image(image, ext.lstrip('.'))
        
        # Convert to base64
        img_str = base64.b64encode(buffer).decode('utf-8')
        
        # Map extension to mime type
        mime_types = {
            ".jpg": "image/jpeg", 
            ".jpeg": "image/jpeg",
            ".png": "image/png",
            ".webp": "image/webp"
        }
        mime_type = mime_types.get(ext.lower(), f"image/{ext[1:].lower()}")
        
        return img_str, mime_type
