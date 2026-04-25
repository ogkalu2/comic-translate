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

DEFAULT_MAX_OUTPUT_TOKENS = 512
REPAIR_MAX_OUTPUT_TOKENS = 1024


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
        self.use_scene_memory = False
        self.interpret_then_translate = False
        self.last_scene_memory = ""
        
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
        self.img_as_llm_input = llm_settings.get(
            'use_page_image_context',
            llm_settings.get('image_input_enabled', True),
        )
        self.temperature = float(llm_settings.get("temperature", 0))
        self.top_p = float(llm_settings.get("top_p", 1))
        self.max_tokens = int(llm_settings.get("max_tokens", DEFAULT_MAX_OUTPUT_TOKENS))
        self.use_scene_memory = bool(llm_settings.get("use_scene_memory", False))
        self.interpret_then_translate = bool(llm_settings.get("interpret_then_translate", False))
        self.last_scene_memory = ""
        self.repetition_penalty = float(llm_settings.get("repetition_penalty", 1.05))
    def _estimate_request_max_tokens(self, blk_list: list[TextBlock]) -> int:
        try:
            total_chars = sum(len(getattr(blk, "text", "") or "") for blk in blk_list)
        except Exception:
            total_chars = 0
        line_count = len(blk_list or [])

        try:
            configured_max_tokens = int(self.max_tokens)
        except (TypeError, ValueError):
            configured_max_tokens = DEFAULT_MAX_OUTPUT_TOKENS

        # Russian and other inflected target languages can be much longer than
        # compact OCR source text. Budget by both source size and line count so
        # multi-bubble pages do not get truncated before the closing JSON.
        # Treat low saved values as legacy defaults, not as a hard cap that can
        # make the structured response impossible to finish.
        max_tokens_cap = max(configured_max_tokens, DEFAULT_MAX_OUTPUT_TOKENS)
        estimated = 512 + (total_chars * 4) + (line_count * 96)
        minimum_for_lines = 512 + (line_count * 192)
        return max(512, min(max_tokens_cap, max(estimated, minimum_for_lines)))

    def _expand_max_tokens_for_structured_retry(
        self,
        current_max_tokens: int,
        estimated_max_tokens: int,
    ) -> int:
        return min(
            REPAIR_MAX_OUTPUT_TOKENS,
            max(
                int(current_max_tokens) * 2,
                int(estimated_max_tokens) + 512,
                1024,
            ),
        )

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
        indexed_lines = [
            {"idx": index, "text": line}
            for index, line in enumerate(lines, start=1)
        ]
        lines_json = dumps_compact_json(indexed_lines)
        line_count = len(lines)
        natural_language_prompt = self.get_system_prompt(self.source_lang, self.target_lang)

        system_prompt = (
            f"{natural_language_prompt} "
            f"Translate ONLY the numbered CURRENT_INPUT items from {self.source_lang} to {self.target_lang}. "
            f"Return exactly one complete minified JSON object: {{\"r\":[...]}}. "
            f"Hard format contract: r has exactly {line_count} strings; r[0] maps to idx 1, r[1] to idx 2; preserve order; "
            f"do not merge, split, add, omit, or translate context/scene-memory/example text as output. "
            f"JSON contract: output JSON only; no markdown; escape raw double quotes inside strings; no literal newlines inside strings; always close every string, ], and }}. "
            f"Quality contract: use context and image only to resolve meaning, speakers, references, ellipsis, tone, sarcasm, and visual ambiguity; "
            f"preserve tone, emotion, and punctuation where natural; translate by communicative intent; "
            f"ensure correct agreement and inflection; prefer neutral or impersonal wording when gender/morphology is unclear; "
            f"do not invent pseudo-words or unsupported details; make each line natural native {self.target_lang} speech."
        )

        if extra_context and extra_context.strip():
            user_prompt = f"{extra_context.strip()}\n{lines_json}"
        else:
            user_prompt = lines_json

        return user_prompt, system_prompt

    def _build_translation_repair_prompt(self, system_prompt: str, expected_count: int) -> str:
        return (
            f"Translate from {self.source_lang} to {self.target_lang}. "
            f"Return ONLY one complete valid minified JSON object: {{\"r\":[...]}}. "
            f"r must contain exactly {expected_count} strings, in input order. "
            f"No markdown, no prose, no context lines as outputs. "
            f"Escape double quotes inside strings. No literal newlines inside strings. "
            f"Finish the response with the closing ]}}."
        )

    def _try_apply_single_block_split_translation(self, blk_list: list[TextBlock], content: str) -> bool:
        if len(blk_list) != 1:
            return False
        try:
            payload = json.loads(content)
        except json.JSONDecodeError:
            return False

        arr = None
        if isinstance(payload, list):
            arr = payload
        elif isinstance(payload, dict):
            arr = payload.get("r")
            if arr is None and len(payload) == 1:
                arr = next(iter(payload.values()))

        if not isinstance(arr, list) or len(arr) <= 1 or not all(isinstance(item, str) for item in arr):
            return False

        blk_list[0].translation = sanitize_translation_result_text(" ".join(item.strip() for item in arr if item.strip()))
        logger.warning(
            "LLM returned %d translations for one block after retry; joined them into the single requested block",
            len(arr),
        )
        return True

    def build_context_interpretation_prompts(
        self,
        blk_list: list[TextBlock],
        extra_context: str,
    ) -> tuple[str, str]:
        lines = get_text_lines_compact(blk_list)
        indexed_lines = [
            {"idx": index, "text": line}
            for index, line in enumerate(lines, start=1)
        ]
        lines_json = dumps_compact_json(indexed_lines)
        line_count = len(lines)
        system_prompt = (
            f"Interpret the current comic page context before translation from {self.source_lang} to {self.target_lang}. "
            f"Return ONLY JSON with this structure: {{\"i\":[<strings>],\"m\":\"<string>\"}}. "
            f"Rules: - the input has exactly {line_count} numbered dialogue items "
            f"- i must contain exactly {line_count} strings, no more and no fewer "
            f"- i[0] must describe idx 1, i[1] must describe idx 2, and so on "
            f"- never merge two input items into one note "
            f"- never omit a note; use \"ambiguous from available context\" when there is not enough context "
            f"- each i item must be a short neutral-English meaning note for the matching input item "
            f"- use previous-page context and any page image only to resolve meaning, referents, sarcasm, ellipsis, and speaker intent "
            f"- explicitly note visual disambiguation when it affects meaning, such as romantic/relationship context versus calendar or scheduling vocabulary "
            f"- if a detail is ambiguous, say so briefly instead of collapsing it into one unsupported interpretation "
            f"- do not invent facts that are not supported by text or image context "
            f"- m must be a compact scene memory for the next page covering speakers, key referents, emotional tone, and what is happening "
            f"- keep m under 240 characters "
            f"- output valid JSON only"
        )
        if extra_context and extra_context.strip():
            user_prompt = f"{extra_context.strip()}\n{lines_json}"
        else:
            user_prompt = lines_json
        return user_prompt, system_prompt

    def _parse_interpretation_content(
        self,
        content: str,
        expected_count: int,
        *,
        allow_repair: bool = False,
    ) -> tuple[list[str], str]:
        payload = json.loads(content)
        interpretations = payload.get("i") or []
        if not isinstance(interpretations, list) or not all(isinstance(item, str) for item in interpretations):
            raise ValueError("Invalid interpretation result format")

        if len(interpretations) != expected_count:
            if not allow_repair:
                raise ValueError(
                    f"Invalid interpretation result length: expected {expected_count}, got {len(interpretations)}"
                )
            logger.warning(
                "Internal interpretation returned %d notes for %d lines after retry; normalizing length",
                len(interpretations),
                expected_count,
            )

        normalized = [item.strip() for item in interpretations[:expected_count]]
        if allow_repair and len(normalized) < expected_count:
            normalized.extend(["ambiguous from available context"] * (expected_count - len(normalized)))

        scene_memory = payload.get("m") or ""
        if not isinstance(scene_memory, str):
            scene_memory = ""
        return normalized, scene_memory.strip()[:240]

    def _build_interpretation_repair_prompt(self, system_prompt: str, expected_count: int) -> str:
        return (
            system_prompt
            + f" CRITICAL FORMAT FIX: return JSON only, with i containing exactly {expected_count} strings. "
            + "Do not combine, split, add, or omit entries. "
            + "If a line is unclear, write \"ambiguous from available context\" for that exact slot."
        )

    def _analyze_page_context(
        self,
        blk_list: list[TextBlock],
        image: np.ndarray,
        extra_context: str,
    ) -> tuple[list[str], str]:
        user_prompt, system_prompt = self.build_context_interpretation_prompts(
            blk_list,
            extra_context,
        )
        expected_count = len(blk_list)
        try:
            first_content = self._perform_translation(user_prompt, system_prompt, image)
            try:
                return self._parse_interpretation_content(first_content, expected_count)
            except (json.JSONDecodeError, ValueError) as exc:
                logger.warning(
                    "Internal interpretation returned invalid context on first attempt; retrying once: %s",
                    exc,
                )
                repair_prompt = self._build_interpretation_repair_prompt(system_prompt, expected_count)
                second_content = self._perform_translation(user_prompt, repair_prompt, image)
                return self._parse_interpretation_content(
                    second_content,
                    expected_count,
                    allow_repair=True,
                )
        except Exception as exc:
            logger.warning(
                "Failed to build internal interpretation context; continuing with direct translation: %s",
                exc,
            )
            return [], ""

    def _append_interpretation_context(
        self,
        extra_context: str,
        blk_list: list[TextBlock],
        interpretation_map: dict[int, str],
    ) -> str:
        if not interpretation_map:
            return extra_context

        notes = []
        for index, blk in enumerate(blk_list, start=1):
            note = (interpretation_map.get(id(blk), "") or "").strip()
            if note:
                notes.append(f"{index}. {note}")

        if not notes:
            return extra_context

        interpretation_block = "Current page meaning notes:\n" + "\n".join(notes)
        if extra_context and extra_context.strip():
            return f"{extra_context.strip()}\n\n{interpretation_block}"
        return interpretation_block

    def _build_fallback_scene_memory(self, blk_list: list[TextBlock]) -> str:
        parts: list[str] = []
        for blk in blk_list:
            text = (getattr(blk, "translation", "") or "").strip() or (getattr(blk, "text", "") or "").strip()
            compact = " ".join(text.split())
            if compact:
                parts.append(compact)
            if len(parts) >= 3:
                break
        return " | ".join(parts)[:240]

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
        retry_prompt = self._build_translation_repair_prompt(system_prompt, len(blk_list))
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
            if interjection_mode:
                self.temperature = 0.3
                self.top_p = 0.9
                self.repetition_penalty = 1.1
            else:
                self.repetition_penalty = 1.05
        try:
            for attempt_index, prompt in enumerate(
                (
                    system_prompt,
                    retry_prompt,
                ),
                start=1,
            ):
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
                    self.max_tokens = self._expand_max_tokens_for_structured_retry(
                        self.max_tokens,
                        estimated_max_tokens,
                    )
                    logger.warning(
                        "LLM translation returned invalid structured output on attempt %d; retrying once with stricter JSON instructions and max_tokens=%s: %s",
                        attempt_index,
                        self.max_tokens,
                        exc,
                    )
        finally:
            self.max_tokens = original_max_tokens
            self.temperature = original_temperature
            self.top_p = original_top_p

        if last_exc is not None and self._try_apply_single_block_split_translation(blk_list, content):
            self._ensure_no_runaway_repetition(blk_list)
            return self._snapshot_usage()

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
        self.last_scene_memory = ""
        risky_blocks = [blk for blk in blk_list if self._is_high_risk_interjection_block(blk)]
        interpreted_scene_memory = ""
        interpretation_map: dict[int, str] = {}

        if self.interpret_then_translate:
            interpretations, interpreted_scene_memory = self._analyze_page_context(
                blk_list,
                image,
                extra_context,
            )
            interpretation_map = {
                id(blk): interpretation
                for blk, interpretation in zip(blk_list, interpretations)
                if interpretation
            }

        if risky_blocks and len(blk_list) > 1:
            normal_blocks = [blk for blk in blk_list if blk not in risky_blocks]
            if normal_blocks:
                usage_items.append(
                    self._translate_group(
                        normal_blocks,
                        image,
                        self._append_interpretation_context(
                            extra_context,
                            normal_blocks,
                            interpretation_map,
                        ),
                        interjection_mode=False,
                    )
                )
            for blk in risky_blocks:
                usage_items.append(
                    self._translate_group(
                        [blk],
                        image,
                        self._append_interpretation_context(
                            extra_context,
                            [blk],
                            interpretation_map,
                        ),
                        interjection_mode=True,
                    )
                )
            self.last_usage = self._merge_usage_snapshots(usage_items)
            if self.use_scene_memory:
                self.last_scene_memory = interpreted_scene_memory or self._build_fallback_scene_memory(blk_list)
            return blk_list

        usage = self._translate_group(
            blk_list,
            image,
            self._append_interpretation_context(
                extra_context,
                blk_list,
                interpretation_map,
            ),
            interjection_mode=(len(blk_list) == 1 and bool(risky_blocks)),
        )
        self.last_usage = usage
        if self.use_scene_memory:
            self.last_scene_memory = interpreted_scene_memory or self._build_fallback_scene_memory(blk_list)
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
