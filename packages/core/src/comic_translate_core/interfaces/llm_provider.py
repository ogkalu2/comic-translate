from abc import ABC, abstractmethod
from typing import List

from ..models import QAChunk, QAPatch


class ILLMProvider(ABC):

    @abstractmethod
    def review_chunk(
        self,
        chunk: QAChunk,
        temperature: float = 0.3,
        max_tokens: int = 4000,
    ) -> List[QAPatch]:
        ...

    @abstractmethod
    def get_model_name(self) -> str:
        ...
