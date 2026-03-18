from dataclasses import dataclass
from typing import Dict, List

from .block import ScriptBlock


@dataclass
class ScriptExport:
    version: str
    comic_id: str
    base_fp: str
    script_id: str
    source_lang: str
    target_lang: str
    exported_at: float
    page_range: List[int]
    active_variant: str
    variants: Dict[str, Dict]
    glossary_snapshot: Dict[str, Dict]
    blocks: List[ScriptBlock]
