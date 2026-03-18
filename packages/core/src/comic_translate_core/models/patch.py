from dataclasses import dataclass
from enum import Enum
from typing import Dict, List


class PatchCategory(str, Enum):
    GLOSSARY_CONSISTENCY = "glossary_consistency"
    TONE = "tone"
    GRAMMAR = "grammar"
    STYLE = "style"
    LOCALIZATION = "localization"


@dataclass
class QAPatch:
    block_id: str
    original: str
    old_translated: str
    new_translated: str
    reason: str
    category: PatchCategory
    confidence: float


@dataclass
class QAPatchSet:
    version: str
    comic_id: str
    base_fp: str
    created_at: float
    qa_model: str
    chunk_range: Dict[str, str]
    summary: Dict
    patches: List[QAPatch]
