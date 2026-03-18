from abc import ABC, abstractmethod
from typing import Optional, List

from ..models import ScriptExport


class IScriptExporter(ABC):

    @abstractmethod
    def export(
        self,
        comic_id: str,
        base_fp: str,
        source_lang: str,
        target_lang: str,
        page_range: Optional[List[int]] = None,
        variant: str = "default",
    ) -> ScriptExport:
        ...
