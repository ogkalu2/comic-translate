import base64
import json
import logging
import re
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
    if not text:
        return ""
    quote_chars = "\"'`‘’‚‛“”„‟«»‹›〝〞＂＇´"
    cleaned = text.translate(str.maketrans("", "", quote_chars))
    cleaned = " ".join(cleaned.split())
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
    try:
        obj = json.loads(content)
    except json.JSONDecodeError as exc:
        log_json_decode_failure("set_translations_from_result_array", content, exc)
        raise
    arr = obj[key]
    if not isinstance(arr, list) or not all(isinstance(x, str) for x in arr):
        raise ValueError(f"Invalid result format: expected {{{json.dumps(key)}:[str,...]}}")

    # жёстко держим длину
    if len(arr) != len(blk_list):
        raise ValueError(f"Length mismatch: got {len(arr)} translations for {len(blk_list)} blocks")

    for i, blk in enumerate(blk_list):
        blk.translation = sanitize_translation_result_text(arr[i])
