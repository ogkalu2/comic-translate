from dataclasses import dataclass
from typing import Dict, List

from .block import ScriptBlock


@dataclass
class QAChunk:
    chunk_id: int
    comic_id: str
    base_fp: str
    source_lang: str
    target_lang: str
    glossary_snapshot: Dict[str, Dict]
    context_blocks: List[ScriptBlock]
    blocks: List[ScriptBlock]
