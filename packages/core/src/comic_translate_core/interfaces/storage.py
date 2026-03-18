from abc import ABC, abstractmethod

from ..models import ScriptExport, QAPatchSet


class IScriptStorage(ABC):

    @abstractmethod
    def save_script(self, script: ScriptExport, path: str) -> None:
        ...

    @abstractmethod
    def load_script(self, path: str) -> ScriptExport:
        ...

    @abstractmethod
    def save_patch(self, patch_set: QAPatchSet, path: str) -> None:
        ...

    @abstractmethod
    def load_patch(self, path: str) -> QAPatchSet:
        ...
