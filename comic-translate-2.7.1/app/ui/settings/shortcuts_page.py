from __future__ import annotations

from PySide6 import QtCore, QtGui, QtWidgets
from PySide6.QtCore import QCoreApplication

from app.shortcuts import get_default_shortcuts, get_shortcut_definitions

from ..dayu_widgets.label import MLabel


class ShortcutsPage(QtWidgets.QWidget):
    shortcut_changed = QtCore.Signal(str, str)
    TRANSLATION_CONTEXT = "ShortcutDefinitions"

    def __init__(self, parent=None):
        super().__init__(parent)
        self._editors: dict[str, QtWidgets.QKeySequenceEdit] = {}
        self._loading = False
        self._init_ui()

    def _init_ui(self) -> None:
        layout = QtWidgets.QVBoxLayout(self)

        title = MLabel(self.tr("Keyboard Shortcuts")).h4()
        note = MLabel(
            self.tr("Assign shortcuts for common editing actions. Leave a field empty to disable that shortcut.")
        ).secondary()
        note.setWordWrap(True)

        layout.addWidget(title)
        layout.addWidget(note)

        grid = QtWidgets.QGridLayout()
        grid.setColumnStretch(1, 1)

        defaults = get_default_shortcuts()
        for row, definition in enumerate(get_shortcut_definitions()):
            label = MLabel(self._translate_definition(definition.label))
            description = MLabel(self._translate_definition(definition.description)).secondary()
            description.setWordWrap(True)

            label_container = QtWidgets.QWidget()
            label_layout = QtWidgets.QVBoxLayout(label_container)
            label_layout.setContentsMargins(0, 0, 0, 0)
            label_layout.addWidget(label)
            label_layout.addWidget(description)

            editor = QtWidgets.QKeySequenceEdit()
            editor.setClearButtonEnabled(True)
            editor.setKeySequence(QtGui.QKeySequence(defaults[definition.id]))
            editor.keySequenceChanged.connect(
                lambda sequence, shortcut_id=definition.id: self._on_sequence_changed(shortcut_id, sequence)
            )
            self._editors[definition.id] = editor

            reset_button = QtWidgets.QPushButton(self.tr("Reset"))
            reset_button.clicked.connect(
                lambda _checked=False, shortcut_id=definition.id: self.reset_shortcut(shortcut_id)
            )

            grid.addWidget(label_container, row, 0)
            grid.addWidget(editor, row, 1)
            grid.addWidget(reset_button, row, 2)

        reset_all_button = QtWidgets.QPushButton(self.tr("Reset All Shortcuts"))
        reset_all_button.clicked.connect(self.reset_all_shortcuts)

        layout.addLayout(grid)
        layout.addWidget(reset_all_button, alignment=QtCore.Qt.AlignmentFlag.AlignLeft)
        layout.addStretch(1)

    def get_shortcuts(self) -> dict[str, str]:
        return {
            shortcut_id: editor.keySequence().toString(QtGui.QKeySequence.SequenceFormat.PortableText)
            for shortcut_id, editor in self._editors.items()
        }

    def load_shortcuts(self, shortcuts: dict[str, str]) -> None:
        self._loading = True
        try:
            for definition in get_shortcut_definitions():
                sequence = shortcuts.get(definition.id, definition.default)
                self._editors[definition.id].setKeySequence(QtGui.QKeySequence(sequence))
        finally:
            self._loading = False

    def reset_shortcut(self, shortcut_id: str) -> None:
        default_sequence = get_default_shortcuts()[shortcut_id]
        self._editors[shortcut_id].setKeySequence(QtGui.QKeySequence(default_sequence))

    def reset_all_shortcuts(self) -> None:
        self.load_shortcuts(get_default_shortcuts())
        for shortcut_id, sequence in self.get_shortcuts().items():
            self.shortcut_changed.emit(shortcut_id, sequence)

    def _on_sequence_changed(self, shortcut_id: str, sequence: QtGui.QKeySequence) -> None:
        if self._loading:
            return
        self.shortcut_changed.emit(
            shortcut_id,
            sequence.toString(QtGui.QKeySequence.SequenceFormat.PortableText),
        )

    @classmethod
    def _translate_definition(cls, text: str) -> str:
        return QCoreApplication.translate(cls.TRANSLATION_CONTEXT, text)
