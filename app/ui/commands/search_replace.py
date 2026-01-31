from __future__ import annotations

from dataclasses import dataclass

from PySide6.QtGui import QUndoCommand


@dataclass(frozen=True)
class ReplaceChange:
    file_path: str
    xyxy: tuple[int, int, int, int]
    angle: float
    old_text: str
    new_text: str
    old_html: str | None = None
    new_html: str | None = None


class ReplaceBlocksCommand(QUndoCommand):
    def __init__(
        self,
        controller,
        *,
        in_target: bool,
        changes: list[ReplaceChange],
        text: str | None = None,
    ):
        super().__init__()
        self._controller = controller
        self._in_target = bool(in_target)
        self._changes = changes
        if text:
            self.setText(text)
        else:
            self.setText("replace_text")

    def _apply(self, use_new: bool):
        for ch in self._changes:
            self._controller._apply_block_text_by_key(
                in_target=self._in_target,
                file_path=ch.file_path,
                xyxy=ch.xyxy,
                angle=ch.angle,
                new_text=ch.new_text if use_new else ch.old_text,
                html_override=ch.new_html if use_new else ch.old_html,
            )

    def redo(self):
        self._apply(True)

    def undo(self):
        self._apply(False)
