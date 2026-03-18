from abc import ABC, abstractmethod
from typing import Iterator

from ..models import ScriptExport, QAChunk


class IChunkingStrategy(ABC):

    @abstractmethod
    def chunk(
        self,
        script: ScriptExport,
        chunk_size: int = 80,
        overlap: int = 5,
    ) -> Iterator[QAChunk]:
        ...
