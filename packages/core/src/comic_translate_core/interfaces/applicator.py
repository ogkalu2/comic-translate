from abc import ABC, abstractmethod
from typing import Dict

from ..models import QAPatchSet


class IPatchApplicator(ABC):

    @abstractmethod
    def apply_patches(
        self,
        patch_set: QAPatchSet,
        dry_run: bool = False,
        confidence_threshold: float = 0.7,
    ) -> Dict:
        ...
