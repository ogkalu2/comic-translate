from __future__ import annotations

from typing import TYPE_CHECKING

from PySide6 import QtCore, QtGui, QtWidgets
from PySide6.QtCore import QSettings

from app.shortcuts import get_default_shortcuts, get_shortcut_definitions

if TYPE_CHECKING:
    from controller import ComicTranslate


class ShortcutController:
    SETTINGS_GROUP = "shortcuts"

    def __init__(self, main: "ComicTranslate"):
        self.main = main
        self._shortcuts: dict[str, QtGui.QShortcut] = {}
        self._register_shortcuts()

    def _register_shortcuts(self) -> None:
        for definition in get_shortcut_definitions():
            shortcut = QtGui.QShortcut(self.main)
            shortcut.setContext(QtCore.Qt.ShortcutContext.WindowShortcut)
            shortcut.activated.connect(
                lambda shortcut_id=definition.id: self._activate_shortcut(shortcut_id)
            )
            self._shortcuts[definition.id] = shortcut

        self.apply_shortcuts()

    def apply_shortcuts(self) -> None:
        current_shortcuts = self.get_current_shortcuts()
        for shortcut_id, shortcut in self._shortcuts.items():
            shortcut.setKey(QtGui.QKeySequence(current_shortcuts.get(shortcut_id, "")))
        self._update_tooltips(current_shortcuts)

    def get_current_shortcuts(self) -> dict[str, str]:
        shortcuts = get_default_shortcuts()
        settings = QSettings("ComicLabs", "ComicTranslate")
        settings.beginGroup(self.SETTINGS_GROUP)
        for definition in get_shortcut_definitions():
            shortcuts[definition.id] = settings.value(
                definition.id,
                shortcuts[definition.id],
                type=str,
            )
        settings.endGroup()
        return shortcuts

    def _activate_shortcut(self, shortcut_id: str) -> None:
        handlers = {
            "undo": self._undo,
            "redo": self._redo,
            "delete_selected_box": self._delete_selected_box,
            "restore_text_blocks": self._restore_text_blocks,
        }
        handler = handlers.get(shortcut_id)
        if handler is not None:
            handler()

    def _workspace_is_active(self) -> bool:
        try:
            return self.main._center_stack.currentWidget() is self.main.main_content_widget
        except Exception:
            return False

    def _is_text_input_focused(self) -> bool:
        focus_widget = QtWidgets.QApplication.focusWidget()
        editable_types = (
            QtWidgets.QLineEdit,
            QtWidgets.QTextEdit,
            QtWidgets.QPlainTextEdit,
            QtWidgets.QAbstractSpinBox,
            QtWidgets.QKeySequenceEdit,
        )
        return isinstance(focus_widget, editable_types)

    def _undo(self) -> None:
        if not self._workspace_is_active() or self._is_text_input_focused():
            return
        stack = self.main.undo_group.activeStack()
        if stack is not None and stack.canUndo():
            self.main.undo_group.undo()

    def _redo(self) -> None:
        if not self._workspace_is_active() or self._is_text_input_focused():
            return
        stack = self.main.undo_group.activeStack()
        if stack is not None and stack.canRedo():
            self.main.undo_group.redo()

    def _delete_selected_box(self) -> None:
        if not self._workspace_is_active() or self._is_text_input_focused():
            return
        self.main.delete_selected_box()

    def _restore_text_blocks(self) -> None:
        if not self._workspace_is_active() or self._is_text_input_focused():
            return
        if self.main.blk_list:
            self.main.pipeline.load_box_coords(self.main.blk_list)

    def _update_tooltips(self, shortcuts: dict[str, str]) -> None:
        delete_sequence = self._format_shortcut(shortcuts.get("delete_selected_box", ""))
        restore_sequence = self._format_shortcut(shortcuts.get("restore_text_blocks", ""))

        delete_tooltip = self.main.tr("Delete Selected Box")
        restore_tooltip = self.main.tr(
            "Draws all the Text Blocks in the existing Text Block List\nback on the Image (for further editing)"
        )

        if delete_sequence:
            delete_tooltip = f"{delete_tooltip} ({delete_sequence})"
        if restore_sequence:
            restore_tooltip = f"{restore_tooltip}\n{self.main.tr('Shortcut')}: {restore_sequence}"

        self.main.delete_button.setToolTip(delete_tooltip)
        self.main.draw_blklist_blks.setToolTip(restore_tooltip)

        try:
            undo_button, redo_button = self.main.undo_tool_group.get_button_group().buttons()[:2]
        except Exception:
            return

        undo_tooltip = self.main.tr("Undo")
        redo_tooltip = self.main.tr("Redo")
        undo_sequence = self._format_shortcut(shortcuts.get("undo", ""))
        redo_sequence = self._format_shortcut(shortcuts.get("redo", ""))
        if undo_sequence:
            undo_tooltip = f"{undo_tooltip} ({undo_sequence})"
        if redo_sequence:
            redo_tooltip = f"{redo_tooltip} ({redo_sequence})"
        undo_button.setToolTip(undo_tooltip)
        redo_button.setToolTip(redo_tooltip)

    @staticmethod
    def _format_shortcut(sequence: str) -> str:
        return QtGui.QKeySequence(sequence).toString(QtGui.QKeySequence.SequenceFormat.NativeText)
