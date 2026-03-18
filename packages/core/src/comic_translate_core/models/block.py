from dataclasses import dataclass
from enum import Enum
from typing import Optional, List


class BlockType(str, Enum):
    DIALOGUE = "dialogue"
    NARRATION = "narration"
    SFX = "sfx"
    CREDIT = "credit"


@dataclass
class BlockContext:
    speaker: Optional[str] = None
    prev_block: Optional[str] = None
    next_block: Optional[str] = None


@dataclass
class ScriptBlock:
    block_id: str
    page: int
    type: BlockType
    bbox: List[int]
    original: str
    translated: str
    original_variant: str
    context: BlockContext
    qa_metadata: Optional[dict] = None
