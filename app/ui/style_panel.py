from __future__ import annotations

from typing import Iterable, Optional

from PySide6 import QtWidgets
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QColor, QFontDatabase

from schemas.style_state import StyleState


class _ColorSwatchButton(QtWidgets.QPushButton):
    colorChanged = Signal(QColor)

    def __init__(self, label: str, parent: Optional[QtWidgets.QWidget] = None):
        super().__init__(label, parent)
        self._color = QColor(255, 255, 255)
        self.setCursor(Qt.PointingHandCursor)
        self.setFixedHeight(28)
        self.clicked.connect(self._on_clicked)
        self._update_style()

    def _update_style(self) -> None:
        self.setStyleSheet(
            "QPushButton {"
            "border: 1px solid rgba(0,0,0,80);"
            "border-radius: 8px;"
            f"background-color: {self._color.name()};"
            "padding: 4px 10px;"
            "text-align: left;"
            "}"
        )

    def color(self) -> QColor:
        return QColor(self._color)

    def setColor(self, color: QColor) -> None:
        if not color.isValid():
            return
        self._color = QColor(color)
        self._update_style()

    def _on_clicked(self) -> None:
        dialog = QtWidgets.QColorDialog(self._color, self)
        dialog.setOption(QtWidgets.QColorDialog.ShowAlphaChannel, False)
        if dialog.exec():
            chosen = dialog.currentColor()
            if chosen.isValid():
                self.setColor(chosen)
                self.colorChanged.emit(chosen)


class StylePanel(QtWidgets.QFrame):
    """Compact Torii-inspired style editor for the active text item."""

    styleChanged = Signal(StyleState)
    reanalyseRequested = Signal()
    fontChanged = Signal(str)
    fontSizeChanged = Signal(int)
    alignmentChanged = Signal(str)

    def __init__(self, parent: Optional[QtWidgets.QWidget] = None):
        super().__init__(parent)
        self.setObjectName("toriiStylePanel")
        self.setFrameShape(QtWidgets.QFrame.StyledPanel)
        self.setFrameShadow(QtWidgets.QFrame.Raised)
        self.setStyleSheet(
            "#toriiStylePanel {"
            "background: rgba(250, 250, 252, 235);"
            "border-radius: 16px;"
            "border: 1px solid rgba(0,0,0,40);"
            "}"
        )

        self._style = StyleState()
        self._blocked = False

        main_layout = QtWidgets.QVBoxLayout(self)
        main_layout.setContentsMargins(16, 16, 16, 16)
        main_layout.setSpacing(10)

        header_row = QtWidgets.QHBoxLayout()
        header_label = QtWidgets.QLabel("Style")
        header_label.setStyleSheet("font-weight: 600; letter-spacing: 0.8px;")
        header_row.addWidget(header_label)
        header_row.addStretch()
        self.auto_color_toggle = QtWidgets.QCheckBox("Auto color")
        self.auto_color_toggle.setChecked(True)
        header_row.addWidget(self.auto_color_toggle)
        self.reanalyse_btn = QtWidgets.QPushButton("Re-analyse")
        self.reanalyse_btn.setCursor(Qt.PointingHandCursor)
        header_row.addWidget(self.reanalyse_btn)
        main_layout.addLayout(header_row)

        font_row = QtWidgets.QHBoxLayout()
        self.font_combo = QtWidgets.QFontComboBox()
        self.font_combo.setMinimumWidth(160)
        font_row.addWidget(self.font_combo)
        self.font_size_spin = QtWidgets.QSpinBox()
        self.font_size_spin.setRange(6, 120)
        self.font_size_spin.setSuffix(" pt")
        self.font_size_spin.setValue(32)
        font_row.addWidget(self.font_size_spin)
        main_layout.addLayout(font_row)

        align_row = QtWidgets.QHBoxLayout()
        self.align_group = QtWidgets.QButtonGroup(self)
        for name, text in (("left", "L"), ("center", "C"), ("right", "R"), ("justify", "J")):
            btn = QtWidgets.QToolButton()
            btn.setText(text)
            btn.setCheckable(True)
            btn.setAutoRaise(True)
            btn.setFixedSize(28, 28)
            btn.setProperty("alignment", name)
            self.align_group.addButton(btn)
            align_row.addWidget(btn)
        align_row.addStretch()
        main_layout.addLayout(align_row)

        text_row = QtWidgets.QHBoxLayout()
        text_label = QtWidgets.QLabel("Text")
        text_label.setMinimumWidth(70)
        self.text_color_btn = _ColorSwatchButton("Colour")
        text_row.addWidget(text_label)
        text_row.addWidget(self.text_color_btn, 1)
        main_layout.addLayout(text_row)

        stroke_row = QtWidgets.QHBoxLayout()
        self.stroke_toggle = QtWidgets.QCheckBox("Outline")
        self.stroke_toggle.setChecked(False)
        self.stroke_color_btn = _ColorSwatchButton("Colour")
        self.stroke_slider = QtWidgets.QSlider(Qt.Horizontal)
        self.stroke_slider.setRange(0, 18)
        self.stroke_slider.setValue(0)
        self.stroke_label = QtWidgets.QLabel("Outline 0 px")
        stroke_row.addWidget(self.stroke_toggle)
        stroke_row.addWidget(self.stroke_color_btn)
        stroke_row.addWidget(self.stroke_label)
        stroke_row.addWidget(self.stroke_slider, 1)
        main_layout.addLayout(stroke_row)

        self._connect_signals()
        self._refresh_enabled_state()
        self.set_available_fonts(QFontDatabase().families())

    # ------------------------------------------------------------------
    # Setup helpers
    def _connect_signals(self) -> None:
        self.font_combo.currentFontChanged.connect(self._on_font_changed)
        self.font_size_spin.valueChanged.connect(self._on_font_size_changed)
        for btn in self.align_group.buttons():
            btn.toggled.connect(self._handle_alignment_button)

        self.text_color_btn.colorChanged.connect(self._on_text_color_changed)
        self.stroke_color_btn.colorChanged.connect(self._on_stroke_color_changed)

        self.auto_color_toggle.toggled.connect(self._on_auto_color_toggled)
        self.stroke_slider.valueChanged.connect(self._on_stroke_size_changed)
        self.stroke_toggle.toggled.connect(self._on_stroke_toggle)
        self.reanalyse_btn.clicked.connect(self.reanalyseRequested.emit)

    # Alignment buttons do not emit IDs by default; hook per-button toggle.
    def _handle_alignment_button(self, checked: bool) -> None:
        if not checked:
            return
        btn = self.sender()
        if not isinstance(btn, QtWidgets.QToolButton):
            return
        alignment = btn.property("alignment") or "left"
        self._style.text_align = alignment
        self.alignmentChanged.emit(alignment)

    def _on_font_size_changed(self, value: int) -> None:
        if self._blocked:
            return
        self._style.font_size = value
        self.fontSizeChanged.emit(value)

    def _on_font_changed(self, font) -> None:
        if self._blocked:
            return
        family = font.family()
        self._style.font_family = family
        self.fontChanged.emit(family)

    def _on_auto_color_toggled(self, checked: bool) -> None:
        if self._blocked:
            return
        self._style.auto_color = checked
        self._refresh_enabled_state()
        self._emit_style()

    def _on_text_color_changed(self, color: QColor) -> None:
        if self._blocked:
            return
        self._style.auto_color = False
        self.auto_color_toggle.setChecked(False)
        self._style.fill = (color.red(), color.green(), color.blue())
        self._emit_style()

    def _on_stroke_color_changed(self, color: QColor) -> None:
        if self._blocked:
            return
        if not self.stroke_toggle.isChecked():
            self.stroke_toggle.setChecked(True)
            return
        self._style.stroke = (color.red(), color.green(), color.blue())
        self._style.stroke_enabled = True
        if self.stroke_slider.value() == 0:
            self.stroke_slider.setValue(max(1, int(round(self._style.font_size / 18 if self._style.font_size else 1))))
        self._emit_style()

    def _on_stroke_toggle(self, checked: bool) -> None:
        if self._blocked:
            return
        if checked and self.auto_color_toggle.isChecked():
            self.auto_color_toggle.setChecked(False)
        self._style.stroke_enabled = checked
        if checked:
            current = self.stroke_color_btn.color()
            if self._style.stroke is None:
                self._style.stroke = (current.red(), current.green(), current.blue())
            if self.stroke_slider.value() == 0:
                base = self._style.font_size or 24
                self.stroke_slider.setValue(max(1, int(round(base / 18))))
        else:
            self._style.stroke_enabled = False
            if self._style.auto_color:
                self._style.stroke = None
                self._style.stroke_size = None
            if self.stroke_slider.value() != 0:
                self.stroke_slider.setValue(0)
        self._refresh_enabled_state()
        self._emit_style()

    def _on_stroke_size_changed(self, value: int) -> None:
        self.stroke_label.setText(f"Outline {value} px")
        if self._blocked:
            return
        if value > 0 and not self.stroke_toggle.isChecked():
            self.stroke_toggle.setChecked(True)
            return
        if value == 0 and self.stroke_toggle.isChecked():
            self.stroke_toggle.setChecked(False)
            return
        self._style.stroke_size = value if value > 0 else None
        self._style.stroke_enabled = value > 0 and self._style.stroke is not None
        self._emit_style()

    def _emit_style(self) -> None:
        self.styleChanged.emit(self._style.copy())

    def _refresh_enabled_state(self) -> None:
        manual_enabled = not self.auto_color_toggle.isChecked()
        self.text_color_btn.setEnabled(manual_enabled)
        stroke_allowed = manual_enabled or self._style.stroke_enabled or self._style.stroke is not None
        self.stroke_toggle.setEnabled(stroke_allowed or self.stroke_toggle.isChecked())
        stroke_active = stroke_allowed and self.stroke_toggle.isChecked()
        self.stroke_color_btn.setEnabled(stroke_active)
        self.stroke_slider.setEnabled(stroke_active)

    # ------------------------------------------------------------------
    # Public API
    def set_available_fonts(self, families: Iterable[str]) -> None:
        current = self.font_combo.currentFont().family()
        self.font_combo.blockSignals(True)
        self.font_combo.clear()
        for family in families:
            self.font_combo.addItem(family)
        if current:
            self.font_combo.setCurrentText(current)
        self.font_combo.blockSignals(False)

    def set_style(self, style: StyleState, font_family: str, font_size: int, alignment: str) -> None:
        self._blocked = True
        try:
            self._style = style.copy()
            self.auto_color_toggle.setChecked(self._style.auto_color)
            if self._style.fill is not None:
                self.text_color_btn.setColor(QColor(*self._style.fill))
            if self._style.stroke is not None:
                self.stroke_color_btn.setColor(QColor(*self._style.stroke))
            self.stroke_toggle.setChecked(bool(self._style.stroke_enabled))
            self.stroke_slider.setValue(int(self._style.stroke_size or 0))
            self.stroke_label.setText(f"Outline {int(self._style.stroke_size or 0)} px")
            self.font_combo.setCurrentText(font_family)
            self.font_size_spin.setValue(max(6, int(font_size)))
            self._select_alignment_button(alignment)
        finally:
            self._blocked = False
        self._refresh_enabled_state()

    def clear_style(self) -> None:
        self._blocked = True
        try:
            self._style = StyleState()
            self.auto_color_toggle.setChecked(True)
            self.stroke_toggle.setChecked(False)
            self.stroke_slider.setValue(0)
            self.stroke_label.setText("Outline 0 px")
        finally:
            self._blocked = False
        self._refresh_enabled_state()

    def _select_alignment_button(self, name: str) -> None:
        mapping = {btn.property("alignment"): btn for btn in self.align_group.buttons()}
        btn = mapping.get(name, mapping.get("left"))
        if btn:
            btn.setChecked(True)


__all__ = ["StylePanel"]
