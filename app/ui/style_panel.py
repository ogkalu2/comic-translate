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

        color_row = QtWidgets.QHBoxLayout()
        self.text_color_btn = _ColorSwatchButton("Text")
        self.stroke_color_btn = _ColorSwatchButton("Stroke")
        self.bg_color_btn = _ColorSwatchButton("Background")
        color_row.addWidget(self.text_color_btn)
        color_row.addWidget(self.stroke_color_btn)
        color_row.addWidget(self.bg_color_btn)
        main_layout.addLayout(color_row)

        stroke_row = QtWidgets.QHBoxLayout()
        self.stroke_slider = QtWidgets.QSlider(Qt.Horizontal)
        self.stroke_slider.setRange(0, 12)
        self.stroke_slider.setValue(0)
        self.stroke_label = QtWidgets.QLabel("Stroke 0 px")
        stroke_row.addWidget(self.stroke_label)
        stroke_row.addWidget(self.stroke_slider)
        main_layout.addLayout(stroke_row)

        bg_opts_row = QtWidgets.QHBoxLayout()
        self.bg_toggle = QtWidgets.QCheckBox("Background")
        self.border_toggle = QtWidgets.QCheckBox("Border")
        bg_opts_row.addWidget(self.bg_toggle)
        bg_opts_row.addWidget(self.border_toggle)
        bg_opts_row.addStretch()
        main_layout.addLayout(bg_opts_row)

        alpha_row = QtWidgets.QHBoxLayout()
        self.bg_alpha_slider = QtWidgets.QSlider(Qt.Horizontal)
        self.bg_alpha_slider.setRange(0, 255)
        self.bg_alpha_slider.setValue(0)
        self.bg_alpha_label = QtWidgets.QLabel("Alpha 0")
        alpha_row.addWidget(self.bg_alpha_label)
        alpha_row.addWidget(self.bg_alpha_slider)
        main_layout.addLayout(alpha_row)

        radius_row = QtWidgets.QHBoxLayout()
        self.radius_slider = QtWidgets.QSlider(Qt.Horizontal)
        self.radius_slider.setRange(0, 60)
        self.radius_slider.setValue(0)
        self.radius_label = QtWidgets.QLabel("Radius 0 px")
        radius_row.addWidget(self.radius_label)
        radius_row.addWidget(self.radius_slider)
        main_layout.addLayout(radius_row)

        padding_row = QtWidgets.QHBoxLayout()
        self.padding_slider = QtWidgets.QSlider(Qt.Horizontal)
        self.padding_slider.setRange(0, 60)
        self.padding_slider.setValue(0)
        self.padding_label = QtWidgets.QLabel("Padding 0 px")
        padding_row.addWidget(self.padding_label)
        padding_row.addWidget(self.padding_slider)
        main_layout.addLayout(padding_row)

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
        self.bg_color_btn.colorChanged.connect(self._on_bg_color_changed)

        self.auto_color_toggle.toggled.connect(self._on_auto_color_toggled)
        self.stroke_slider.valueChanged.connect(self._on_stroke_size_changed)
        self.bg_toggle.toggled.connect(self._on_bg_toggle)
        self.border_toggle.toggled.connect(self._on_border_toggle)
        self.bg_alpha_slider.valueChanged.connect(self._on_bg_alpha_changed)
        self.radius_slider.valueChanged.connect(self._on_radius_changed)
        self.padding_slider.valueChanged.connect(self._on_padding_changed)
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
        self._style.stroke = (color.red(), color.green(), color.blue())
        self._style.stroke_enabled = True
        if self.stroke_slider.value() == 0:
            self.stroke_slider.setValue(max(1, int(round(self._style.font_size / 18 if self._style.font_size else 1))))
        self._emit_style()

    def _on_bg_color_changed(self, color: QColor) -> None:
        if self._blocked:
            return
        self._style.bg_color = (color.red(), color.green(), color.blue())
        if not self.bg_toggle.isChecked():
            self.bg_toggle.setChecked(True)
        self._emit_style()

    def _on_stroke_size_changed(self, value: int) -> None:
        self.stroke_label.setText(f"Stroke {value} px")
        if self._blocked:
            return
        self._style.stroke_size = value if value > 0 else None
        self._style.stroke_enabled = value > 0 and self._style.stroke is not None
        self._emit_style()

    def _on_bg_toggle(self, checked: bool) -> None:
        if self._blocked:
            return
        self._style.bg_enabled = checked
        self._refresh_enabled_state()
        self._emit_style()

    def _on_border_toggle(self, checked: bool) -> None:
        if self._blocked:
            return
        self._style.border_enabled = checked
        self._refresh_enabled_state()
        self._emit_style()

    def _on_bg_alpha_changed(self, value: int) -> None:
        self.bg_alpha_label.setText(f"Alpha {value}")
        if self._blocked:
            return
        self._style.bg_alpha = value
        self._emit_style()

    def _on_radius_changed(self, value: int) -> None:
        self.radius_label.setText(f"Radius {value} px")
        if self._blocked:
            return
        self._style.border_radius = value
        self._emit_style()

    def _on_padding_changed(self, value: int) -> None:
        self.padding_label.setText(f"Padding {value} px")
        if self._blocked:
            return
        self._style.border_padding = value
        self._emit_style()

    def _emit_style(self) -> None:
        self.styleChanged.emit(self._style.copy())

    def _refresh_enabled_state(self) -> None:
        manual_enabled = not self.auto_color_toggle.isChecked()
        self.text_color_btn.setEnabled(manual_enabled)
        self.stroke_color_btn.setEnabled(manual_enabled)
        stroke_controls = manual_enabled or (self._style.stroke is not None)
        self.stroke_slider.setEnabled(stroke_controls)
        self.bg_color_btn.setEnabled(self.bg_toggle.isChecked())
        alpha_enabled = self.bg_toggle.isChecked()
        self.bg_alpha_slider.setEnabled(alpha_enabled)
        self.padding_slider.setEnabled(alpha_enabled or self.border_toggle.isChecked())
        self.radius_slider.setEnabled(alpha_enabled or self.border_toggle.isChecked())

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
            if self._style.bg_color is not None:
                self.bg_color_btn.setColor(QColor(*self._style.bg_color))
            self.stroke_slider.setValue(int(self._style.stroke_size or 0))
            self.stroke_label.setText(f"Stroke {int(self._style.stroke_size or 0)} px")
            self.bg_toggle.setChecked(bool(self._style.bg_enabled))
            self.border_toggle.setChecked(bool(self._style.border_enabled))
            self.bg_alpha_slider.setValue(int(self._style.bg_alpha))
            self.bg_alpha_label.setText(f"Alpha {int(self._style.bg_alpha)}")
            self.radius_slider.setValue(int(self._style.border_radius))
            self.radius_label.setText(f"Radius {int(self._style.border_radius)} px")
            self.padding_slider.setValue(int(self._style.border_padding))
            self.padding_label.setText(f"Padding {int(self._style.border_padding)} px")
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
            self.stroke_slider.setValue(0)
            self.stroke_label.setText("Stroke 0 px")
            self.bg_toggle.setChecked(False)
            self.border_toggle.setChecked(False)
            self.bg_alpha_slider.setValue(0)
            self.bg_alpha_label.setText("Alpha 0")
            self.radius_slider.setValue(0)
            self.radius_label.setText("Radius 0 px")
            self.padding_slider.setValue(0)
            self.padding_label.setText("Padding 0 px")
        finally:
            self._blocked = False
        self._refresh_enabled_state()

    def _select_alignment_button(self, name: str) -> None:
        mapping = {btn.property("alignment"): btn for btn in self.align_group.buttons()}
        btn = mapping.get(name, mapping.get("left"))
        if btn:
            btn.setChecked(True)


__all__ = ["StylePanel"]
