import ast
import base64
import json
import logging
import re
from collections import Counter
import jieba
import janome.tokenizer
import numpy as np
from pythainlp.tokenize import word_tokenize
from .textblock import TextBlock
import imkit as imk


MODEL_MAP = {
    "Custom": "",  
    "Deepseek-v3": "deepseek-chat", 
    "GPT-4.1": "gpt-4.1",
    "GPT-4.1-mini": "gpt-4.1-mini",
    "Claude-4.5-Sonnet": "claude-sonnet-4-5-20250929",
    "Claude-4.5-Haiku": "claude-haiku-4-5-20251001",
    "Gemini-2.0-Flash": "gemini-2.0-flash",
    "Gemini-3.0-Flash": "gemini-3-flash-preview",
    "Gemini-2.5-Pro": "gemini-2.5-pro"
}

HTML_TEXT_SPLIT_RE = re.compile(r"(<[^>]+>|&[A-Za-z0-9#]+;)")
logger = logging.getLogger(__name__)
RUNAWAY_REPEAT_RE = re.compile(r"(.)\1{11,}", re.DOTALL)
INTERJECTION_REPEAT_RE = re.compile(r"(.)\1{2,}", re.DOTALL)


def _json_decode_error_preview(content: str, exc: json.JSONDecodeError, radius: int = 160) -> str:
    text = content if isinstance(content, str) else str(content)
    if not text:
        return "<empty>"

    pos = getattr(exc, "pos", -1)
    if pos < 0:
        return text[: radius * 2]

    start = max(0, pos - radius)
    end = min(len(text), pos + radius)
    return text[start:end]


def log_json_decode_failure(context: str, content: str, exc: json.JSONDecodeError) -> None:
    preview = _json_decode_error_preview(content, exc)
    logger.error(
        "%s JSON decode failed at line %s col %s pos %s: %s | raw preview: %r",
        context,
        getattr(exc, "lineno", "?"),
        getattr(exc, "colno", "?"),
        getattr(exc, "pos", "?"),
        getattr(exc, "msg", str(exc)),
        preview,
    )


def _strip_code_fences(text: str) -> str:
    stripped = text.strip()
    if stripped.startswith("```"):
        stripped = re.sub(
            r"^```(?:json)?\s*|\s*```$",
            "",
            stripped,
            flags=re.IGNORECASE | re.DOTALL,
        ).strip()
    return stripped


def _parse_loose_json(content: str):
    if content is None:
        return None

    text = _strip_code_fences(str(content))
    if not text:
        return None

    candidates = [text]
    for pattern in (r"\{[\s\S]*\}", r"\[[\s\S]*\]"):
        match = re.search(pattern, text)
        if match:
            candidates.append(match.group(0))

    for candidate in candidates:
        cleaned = re.sub(r",(\s*[}\]])", r"\1", candidate)
        for parser in (json.loads, ast.literal_eval):
            try:
                return parser(cleaned)
            except Exception:
                continue

    return None


def _decode_json_string_fragment(fragment: str) -> str:
    try:
        return json.loads(f'"{fragment}"')
    except Exception:
        return (
            fragment.replace('\\"', '"')
            .replace("\\n", "\n")
            .replace("\\r", "\r")
            .replace("\\t", "\t")
            .replace("\\\\", "\\")
        )


def _parse_json_like_string_array(
    content: str,
    *,
    key: str = "r",
    expected_count: int | None = None,
) -> list[str] | None:
    """
    Recover a complete JSON-like string array from common LLM mistakes.

    This is intentionally conservative: it only accepts quoted string items and,
    when expected_count is provided, only returns a result with exactly that many
    items. Truncated responses still fail and are retried/chunked by callers.
    """
    if content is None:
        return None

    text = _strip_code_fences(str(content))
    if not text:
        return None

    key_pattern = rf'"{re.escape(key)}"\s*:\s*\['
    key_match = re.search(key_pattern, text)
    if key_match:
        segment = text[key_match.end():]
    else:
        array_start = text.find("[")
        if array_start < 0:
            return None
        segment = text[array_start + 1:]

    values: list[str] = []
    pos = 0
    while pos < len(segment):
        quote_pos = segment.find('"', pos)
        if quote_pos < 0:
            break

        i = quote_pos + 1
        chars: list[str] = []
        closed = False
        while i < len(segment):
            ch = segment[i]
            if ch == "\\":
                if i + 1 < len(segment):
                    chars.append(ch)
                    chars.append(segment[i + 1])
                    i += 2
                    continue
                chars.append(ch)
                i += 1
                continue

            if ch == '"':
                j = i + 1
                while j < len(segment) and segment[j].isspace():
                    j += 1
                if j >= len(segment) or segment[j] in ",]}":
                    values.append(_decode_json_string_fragment("".join(chars)))
                    pos = j + 1
                    closed = True
                    break

                # Treat raw quotes inside a translation as text. This handles
                # model output such as "Он сказал "нет" вчера", which is invalid
                # JSON but still has an unambiguous array delimiter later.
                chars.append(ch)
                i += 1
                continue

            chars.append(ch)
            i += 1

        if not closed:
            break
        if expected_count is not None and len(values) > expected_count:
            return None

    if expected_count is not None and len(values) != expected_count:
        return None
    return values or None

def encode_image_array(img_array: np.ndarray):
    img_bytes = imk.encode_image(img_array, ".png")
    return base64.b64encode(img_bytes).decode('utf-8')

def get_raw_text(blk_list: list[TextBlock]):
    rw_txts_dict = {}
    for idx, blk in enumerate(blk_list):
        block_key = f"block_{idx}"
        rw_txts_dict[block_key] = blk.text
    
    raw_texts_json = json.dumps(rw_txts_dict, ensure_ascii=False, indent=4)
    
    return raw_texts_json

def get_raw_translation(blk_list: list[TextBlock]):
    rw_translations_dict = {}
    for idx, blk in enumerate(blk_list):
        block_key = f"block_{idx}"
        rw_translations_dict[block_key] = blk.translation
    
    raw_translations_json = json.dumps(rw_translations_dict, ensure_ascii=False, indent=4)
    
    return raw_translations_json

def set_texts_from_json(blk_list: list[TextBlock], json_string: str):
    match = re.search(r"\{[\s\S]*\}", json_string)
    if match:
        # Extract the JSON string from the matched regular expression
        json_string = match.group(0)
        try:
            translation_dict = json.loads(json_string)
        except json.JSONDecodeError as exc:
            log_json_decode_failure("set_texts_from_json", json_string, exc)
            raise
        
        for idx, blk in enumerate(blk_list):
            block_key = f"block_{idx}"
            if block_key in translation_dict:
                blk.translation = translation_dict[block_key]
            else:
                print(f"Warning: {block_key} not found in JSON string.")
    else:
        print("No JSON found in the input string.")

def set_upper_case(blk_list: list[TextBlock], upper_case: bool):
    for blk in blk_list:
        translation = blk.translation
        if translation is None:
            continue
        cleaned = normalize_translation_result_text(translation, upper_case=upper_case)
        blk.translation = cleaned

def get_chinese_tokens(text):
    return list(jieba.cut(text, cut_all=False))

def get_japanese_tokens(text):
    tokenizer = janome.tokenizer.Tokenizer()
    return [token.surface for token in tokenizer.tokenize(text)]

def format_translations(blk_list: list[TextBlock], trg_lng_cd: str, upper_case: bool = True):
    for blk in blk_list:
        translation = blk.translation
        if translation is None:
            continue
        trg_lng_code_lower = trg_lng_cd.lower()
        seg_result = []

        if 'zh' in trg_lng_code_lower:
            seg_result = get_chinese_tokens(translation)

        elif 'ja' in trg_lng_code_lower:
            seg_result = get_japanese_tokens(translation)

        elif 'th' in trg_lng_code_lower:
            seg_result = word_tokenize(translation)

        if seg_result:
            blk.translation = normalize_translation_result_text(
                ''.join(word if word in ['.', ','] else f' {word}' for word in seg_result),
                upper_case=True,
            )
        else:
            # Apply whitespace cleanup and force uppercase for rendered text.
            blk.translation = normalize_translation_result_text(
                translation,
                upper_case=True,
            )

def is_there_text(blk_list: list[TextBlock]) -> bool:
    return any(blk.text for blk in blk_list)


def sanitize_translation_source_text(text: str) -> str:
    if text is None:
        return ""
    cleaned = str(text).replace("\r\n", "\n").replace("\r", "\n")
    cleaned = cleaned.replace("\x00", "")
    return cleaned.strip()


def sanitize_translation_source_blocks(blk_list: list[TextBlock]) -> list[TextBlock]:
    for blk in blk_list:
        blk.text = sanitize_translation_source_text(getattr(blk, "text", ""))
        texts = getattr(blk, "texts", None)
        if texts is not None:
            blk.texts = [
                sanitized
                for sanitized in (
                    sanitize_translation_source_text(text) for text in texts
                )
                if sanitized
            ]
    return blk_list


def sanitize_translation_result_text(text: str) -> str:
    if not text:
        return ""
    return normalize_translation_result_text(text, upper_case=False)


def has_runaway_single_char_repetition(text: str) -> bool:
    if not text:
        return False

    compact = re.sub(r"\s+", "", str(text))
    if len(compact) < 16:
        return False

    if RUNAWAY_REPEAT_RE.search(compact):
        return True

    counts = Counter(compact)
    if not counts:
        return False

    _char, count = counts.most_common(1)[0]
    return count >= 14 and (count / len(compact)) >= 0.75


def is_high_risk_sound_effect_text(text: str) -> bool:
    if not text:
        return False

    compact = re.sub(r"\s+", "", str(text))
    if len(compact) < 4:
        return False

    if has_runaway_single_char_repetition(compact):
        return True

    alpha_chars = [ch for ch in compact if ch.isalpha()]
    if not alpha_chars:
        return False

    has_emphasis = any(ch in compact for ch in "!?！？…")
    unique_alpha = len(set(alpha_chars))

    if len(alpha_chars) <= 24 and has_emphasis and INTERJECTION_REPEAT_RE.search(compact):
        return True

    if (
        len(alpha_chars) <= 18
        and has_emphasis
        and compact.upper() == compact
        and unique_alpha <= 3
    ):
        return True

    return False


def normalize_translation_result_text(text: str, upper_case: bool = True) -> str:
    if not text:
        return ""

    cleaned = " ".join(str(text).split())
    cleaned = cleaned.strip()
    if upper_case:
        cleaned = cleaned.upper()
    return cleaned


def transform_text_case_preserving_html(text: str, upper_case: bool = True) -> str:
    """Apply case conversion to text while leaving HTML tags/entities intact."""
    if not text:
        return ""

    parts = HTML_TEXT_SPLIT_RE.split(str(text))
    transformed = []
    for part in parts:
        if not part:
            continue
        if part.startswith("<") and part.endswith(">"):
            transformed.append(part)
            continue
        if part.startswith("&") and part.endswith(";"):
            transformed.append(part)
            continue
        transformed.append(part.upper() if upper_case else part.lower())
    return "".join(transformed)


def sanitize_translation_result_blocks(blk_list: list[TextBlock]) -> list[TextBlock]:
    for blk in blk_list:
        blk.translation = sanitize_translation_result_text(
            getattr(blk, "translation", "")
        )
    return blk_list

import json
from typing import List
from .textblock import TextBlock

def get_text_lines_compact(blk_list: list[TextBlock]) -> List[str]:
    """
    Минимальный по токенам вход для LLM: массив строк без ключей block_i.
    """
    sanitize_translation_source_blocks(blk_list)
    return [(blk.text or "") for blk in blk_list]

def dumps_compact_json(obj) -> str:
    """
    Компактный JSON без пробелов: экономит токены в prompt.
    """
    return json.dumps(obj, ensure_ascii=False, separators=(",", ":"))

def set_translations_from_result_array(blk_list: list[TextBlock], content: str, key: str = "r") -> None:
    """
    Ожидает строгий JSON object формата {"r":[...]} (ключ по умолчанию 'r').
    Маппинг по индексу блока.
    """
    obj = None
    try:
        obj = json.loads(content)
    except json.JSONDecodeError as exc:
        obj = _parse_loose_json(content)
        if obj is None:
            arr = _parse_json_like_string_array(
                content,
                key=key,
                expected_count=len(blk_list),
            )
            if arr is None:
                log_json_decode_failure("set_translations_from_result_array", content, exc)
                raise
            obj = {key: arr}

    if isinstance(obj, list):
        arr = obj
    elif isinstance(obj, dict):
        arr = obj.get(key)
        if arr is None and len(obj) == 1:
            arr = next(iter(obj.values()))
    else:
        arr = None

    if not isinstance(arr, list) or not all(isinstance(x, str) for x in arr):
        arr = _parse_json_like_string_array(
            content,
            key=key,
            expected_count=len(blk_list),
        )
        if arr is None:
            raise ValueError(f"Invalid result format: expected {{{json.dumps(key)}:[str,...]}}")

    # жёстко держим длину
    if len(arr) != len(blk_list):
        raise ValueError(f"Length mismatch: got {len(arr)} translations for {len(blk_list)} blocks")

    for i, blk in enumerate(blk_list):
        blk.translation = sanitize_translation_result_text(arr[i])
