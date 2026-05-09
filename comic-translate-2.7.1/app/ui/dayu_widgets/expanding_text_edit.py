#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""MExpandingTextEdit
A text input that expands vertically up to a maximum number of lines,
then scrolls with the cursor visible at the bottom.
"""
from __future__ import annotations

from PySide6 import QtCore, QtGui, QtWidgets

from . import dayu_theme


class MExpandingTextEdit(QtWidgets.QPlainTextEdit):
    """
    A plain text edit that:
    - Starts with single-line height
    - Expands vertically as text wraps (up to max_lines)
    - After max_lines, scrolls to keep the cursor visible
    - Emits returnPressed when Enter is pressed (Shift+Enter for newline)
    """

    returnPressed = QtCore.Signal()
    textChanged = QtCore.Signal()

    def __init__(self, text: str = "", parent=None, max_lines: int = 4):
        super().__init__(parent)
        self._max_lines = max_lines
        self._dayu_size = dayu_theme.default_size
        self._placeholder_text = ""
        
        # Setup document and viewport
        self.setPlainText(text)
        self.setVerticalScrollBarPolicy(QtCore.Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setHorizontalScrollBarPolicy(QtCore.Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setLineWrapMode(QtWidgets.QPlainTextEdit.LineWrapMode.WidgetWidth)
        self.setSizePolicy(QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Fixed)
        
        # Reduce document margin for compact appearance
        self.document().setDocumentMargin(2)
        
        # Connect signals
        self.document().contentsChanged.connect(self._on_contents_changed)
        self.document().contentsChanged.connect(self.textChanged.emit)
        
        # Set initial height
        QtCore.QTimer.singleShot(0, self._update_height)

    def _on_contents_changed(self):
        """Update height when content changes and ensure cursor is visible."""
        self._update_height()
        # Scroll to ensure cursor is visible at bottom
        QtCore.QTimer.singleShot(0, self._ensure_cursor_visible)

    def _ensure_cursor_visible(self):
        """Scroll so that the cursor (latest input) is visible."""
        self.ensureCursorVisible()

    def _calculate_height_for_lines(self, num_lines: int) -> int:
        """Calculate the widget height for a given number of lines."""
        fm = self.fontMetrics()
        line_height = fm.lineSpacing()
        
        # Minimal padding for compact single-line appearance
        vertical_padding = 6  # Small padding top + bottom
        
        # Calculate total height
        text_height = line_height * num_lines
        total_height = int(text_height + vertical_padding)
        return total_height

    def _update_height(self):
        """Adjust widget height based on content, up to max_lines."""
        doc = self.document()
        text = self.toPlainText()
        
        # If empty, use single line
        if not text:
            self.setFixedHeight(self._calculate_height_for_lines(1))
            self.setVerticalScrollBarPolicy(QtCore.Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
            return
        
        # Count actual visual lines (accounting for word wrap)
        block = doc.firstBlock()
        total_lines = 0
        
        while block.isValid():
            layout = block.layout()
            if layout and layout.lineCount() > 0:
                total_lines += layout.lineCount()
            else:
                total_lines += 1
            block = block.next()
        
        # Ensure at least 1 line
        total_lines = max(1, total_lines)
        
        # Clamp to [1, max_lines]
        visible_lines = min(total_lines, self._max_lines)
        
        new_height = self._calculate_height_for_lines(visible_lines)
        
        # Set fixed height to prevent layout jumping
        self.setFixedHeight(new_height)
        
        # Show/hide scrollbar based on whether content exceeds max lines
        if total_lines > self._max_lines:
            self.setVerticalScrollBarPolicy(QtCore.Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        else:
            self.setVerticalScrollBarPolicy(QtCore.Qt.ScrollBarPolicy.ScrollBarAlwaysOff)

    def keyPressEvent(self, event: QtGui.QKeyEvent):
        """Handle Enter key to emit returnPressed signal."""
        if event.key() in (QtCore.Qt.Key.Key_Return, QtCore.Qt.Key.Key_Enter):
            if event.modifiers() & QtCore.Qt.KeyboardModifier.ShiftModifier:
                # Shift+Enter inserts a newline
                super().keyPressEvent(event)
            else:
                # Plain Enter emits returnPressed (like QLineEdit)
                self.returnPressed.emit()
                return
        else:
            super().keyPressEvent(event)

    def text(self) -> str:
        """Return the plain text content (QLineEdit compatibility)."""
        return self.toPlainText()

    def setText(self, text: str):
        """Set the plain text content (QLineEdit compatibility)."""
        self.setPlainText(text)
        self._update_height()

    def clear(self):
        """Clear the text content."""
        super().clear()
        self._update_height()

    def setPlaceholderText(self, text: str):
        """Set placeholder text (QLineEdit compatibility)."""
        self._placeholder_text = text
        super().setPlaceholderText(text)

    def placeholderText(self) -> str:
        """Get placeholder text."""
        return self._placeholder_text

    def selectAll(self):
        """Select all text (QLineEdit compatibility)."""
        cursor = self.textCursor()
        cursor.select(QtGui.QTextCursor.SelectionType.Document)
        self.setTextCursor(cursor)

    def resizeEvent(self, event):
        """Recalculate height when widget is resized."""
        super().resizeEvent(event)
        self._update_height()

    def showEvent(self, event):
        """Recalculate height when widget becomes visible."""
        super().showEvent(event)
        QtCore.QTimer.singleShot(0, self._update_height)

    # Size methods for dayu_widgets compatibility
    def get_dayu_size(self):
        return self._dayu_size

    def set_dayu_size(self, value):
        self._dayu_size = value
        self.style().polish(self)

    dayu_size = QtCore.Property(int, get_dayu_size, set_dayu_size)

    def huge(self):
        self.set_dayu_size(dayu_theme.huge)
        return self

    def large(self):
        self.set_dayu_size(dayu_theme.large)
        return self

    def medium(self):
        self.set_dayu_size(dayu_theme.medium)
        return self

    def small(self):
        self.set_dayu_size(dayu_theme.small)
        return self

    def tiny(self):
        self.set_dayu_size(dayu_theme.tiny)
        return self

    def sizeHint(self) -> QtCore.QSize:
        """Return size hint based on single line height."""
        width = super().sizeHint().width()
        height = self._calculate_height_for_lines(1)
        return QtCore.QSize(width, height)

    def minimumSizeHint(self) -> QtCore.QSize:
        """Return minimum size hint based on single line height."""
        width = super().minimumSizeHint().width()
        height = self._calculate_height_for_lines(1)
        return QtCore.QSize(width, height)
