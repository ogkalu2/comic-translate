from dataclasses import dataclass, field
from enum import Enum
from typing import List, Dict, Optional

class BlockType(str, Enum):
    DIALOGUE = "dialogue"
    NARRATION = "narration"
    SFX = "sfx"
    CREDIT = "credit"
    UI_META = "ui_meta"

class TranslationStatus(str, Enum):
    """Status of a translation version."""
    APPROVED = "approved"
    REFERENCE = "reference"
    PENDING_REVIEW = "pending_review"

class TranslationSource(str, Enum):
    """Source of a translation."""
    PIPELINE = "pipeline"
    MT = "mt"
    HUMAN = "human"
    REFERENCE_APPLIED = "reference_applied"

@dataclass
class OriginalText:
    variant_id: str
    lang: str
    text: str

@dataclass
class TranslationHistory:
    action: str  # "translate", "reference_applied", "manual_edit"
    source: TranslationSource
    timestamp: Optional[float] = None

@dataclass
class TranslationVersion:
    text: str
    status: TranslationStatus
    weight: float = 1.0
    history: List[TranslationHistory] = field(default_factory=list)
    source: Optional[TranslationSource] = None

@dataclass
class SemanticRouting:
    ner_entities: List[Dict] = field(default_factory=list)
    sfx_detected: bool = False
    route: str = ""

@dataclass
class Block:
    block_uid: str
    nsfw_flag: bool
    type: BlockType
    bbox: List[int]
    original_texts: List[OriginalText]
    translations: Dict[str, Dict[str, TranslationVersion]]
    semantic_routing: Optional[SemanticRouting]
    embedding: Optional[List[float]]
