"""Tool Presets panel widget for the typesetter workflow.

Displays a list of presets organized by category inside a left-panel
tab. The typesetter clicks a preset to instantly apply a full set of
text formatting properties (font, size, color, outline, alignment, etc.).
"""

from __future__ import annotations

import os
from typing import TYPE_CHECKING

from PySide6 import QtCore, QtGui, QtWidgets
from PySide6.QtCore import Signal

from app.ui.dayu_widgets.combo_box import MComboBox
from app.ui.dayu_widgets.divider import MDivider
from app.ui.dayu_widgets.label import MLabel
from app.ui.dayu_widgets.push_button import MPushButton
from app.ui.dayu_widgets.tool_button import MToolButton

from .preset_model import PresetManager, ToolPreset

if TYPE_CHECKING:
    pass


class PresetListItem(QtWidgets.QWidget):
    """Custom list-item widget showing a font icon and preset name."""

    clicked = Signal()

    def __init__(self, preset: ToolPreset, parent=None):
        super().__init__(parent)
        self.preset = preset

        layout = QtWidgets.QHBoxLayout(self)
        layout.setContentsMargins(6, 3, 6, 3)
        layout.setSpacing(6)

        # Font preview icon — show "A" in the preset's font
        self.icon_label = QtWidgets.QLabel("A")
        self.icon_label.setFixedSize(22, 22)
        self.icon_label.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
        self._apply_icon_style()

        # Preset name
        self.name_label = QtWidgets.QLabel(preset.name)
        self.name_label.setStyleSheet("font-size: 12px;")

        layout.addWidget(self.icon_label)
        layout.addWidget(self.name_label)
        layout.addStretch()

    def _apply_icon_style(self):
        p = self.preset
        weight = "bold" if p.bold else "normal"
        style = "italic" if p.italic else "normal"
        self.icon_label.setStyleSheet(
            f"font-family: '{p.font_family}';"
            f"font-size: 14px;"
            f"font-weight: {weight};"
            f"font-style: {style};"
            f"color: {p.color};"
            f"background-color: rgba(255,255,255,15);"
            f"border-radius: 3px;"
        )


class PresetPanel(QtWidgets.QWidget):
    """Panel for managing and applying tool presets.

    Lives inside a tab in the left panel, alongside the Pages tab.
    """

    # Emitted when user clicks a preset; payload is the ToolPreset to apply
    preset_applied = Signal(object)
    # Emitted when user wants to save current toolbar state
    capture_requested = Signal(str)  # preset name
    # Emitted when fonts are imported (list of absolute paths)
    fonts_imported = Signal(list)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._manager = PresetManager()

        self._build_ui()
        self._populate_categories()
        self._connect_signals()

    # ── UI construction ──────────────────────────────────────────────

    def _build_ui(self):
        main_layout = QtWidgets.QVBoxLayout(self)
        main_layout.setContentsMargins(4, 4, 4, 4)
        main_layout.setSpacing(4)

        # ── Category selector row ────────────────────────────────────
        cat_layout = QtWidgets.QHBoxLayout()
        cat_layout.setSpacing(2)

        self._category_combo = MComboBox().small()
        self._category_combo.setToolTip(self.tr("Select preset category"))
        self._category_combo.setMinimumWidth(60)

        self._add_cat_btn = MToolButton()
        self._add_cat_btn.set_dayu_svg("add_line.svg")
        self._add_cat_btn.setToolTip(self.tr("Create new category"))

        self._del_cat_btn = MToolButton()
        self._del_cat_btn.set_dayu_svg("minus_line.svg")
        self._del_cat_btn.setToolTip(self.tr("Delete current category"))

        self._rename_cat_btn = MToolButton()
        self._rename_cat_btn.set_dayu_svg("settings.svg")
        self._rename_cat_btn.setToolTip(self.tr("Rename current category"))

        cat_layout.addWidget(self._category_combo, 1)
        cat_layout.addWidget(self._add_cat_btn)
        cat_layout.addWidget(self._rename_cat_btn)
        cat_layout.addWidget(self._del_cat_btn)

        main_layout.addLayout(cat_layout)

        # ── Action buttons row ───────────────────────────────────────
        action_layout = QtWidgets.QHBoxLayout()
        action_layout.setSpacing(2)

        self._add_preset_btn = MToolButton()
        self._add_preset_btn.set_dayu_svg("add_line.svg")
        self._add_preset_btn.setToolTip(self.tr("Save current settings as a new preset"))

        self._import_fonts_btn = MToolButton()
        self._import_fonts_btn.set_dayu_svg("folder-open.svg")
        self._import_fonts_btn.setToolTip(self.tr("Import font files into this category"))

        self._delete_preset_btn = MToolButton()
        self._delete_preset_btn.set_dayu_svg("trash_line.svg")
        self._delete_preset_btn.setToolTip(self.tr("Delete selected preset"))

        action_layout.addStretch()
        action_layout.addWidget(self._add_preset_btn)
        action_layout.addWidget(self._import_fonts_btn)
        action_layout.addWidget(self._delete_preset_btn)

        main_layout.addLayout(action_layout)

        # ── Preset list (fills remaining space) ──────────────────────
        self._preset_list = QtWidgets.QListWidget()
        self._preset_list.setSelectionMode(
            QtWidgets.QAbstractItemView.SelectionMode.SingleSelection
        )
        self._preset_list.setContextMenuPolicy(
            QtCore.Qt.ContextMenuPolicy.CustomContextMenu
        )
        self._preset_list.setFocusPolicy(QtCore.Qt.FocusPolicy.NoFocus)
        self._preset_list.setStyleSheet(
            "QListWidget { border: 1px solid rgba(255,255,255,20); border-radius: 4px; }"
            "QListWidget::item { padding: 2px 0; }"
            "QListWidget::item:selected { background-color: rgba(64,158,255,60); }"
            "QListWidget::item:hover { background-color: rgba(255,255,255,10); }"
        )

        main_layout.addWidget(self._preset_list, 1)  # stretch=1 fills space

    def _connect_signals(self):
        self._add_preset_btn.clicked.connect(self._on_add_preset)
        self._import_fonts_btn.clicked.connect(self._on_import_fonts)
        self._delete_preset_btn.clicked.connect(self._on_delete_preset)
        self._add_cat_btn.clicked.connect(self._on_add_category)
        self._del_cat_btn.clicked.connect(self._on_delete_category)
        self._rename_cat_btn.clicked.connect(self._on_rename_category)
        self._category_combo.currentTextChanged.connect(self._on_category_changed)
        self._preset_list.itemClicked.connect(self._on_preset_clicked)
        self._preset_list.customContextMenuRequested.connect(self._show_context_menu)

    # ── Populate ─────────────────────────────────────────────────────

    def _populate_categories(self):
        self._category_combo.blockSignals(True)
        self._category_combo.clear()
        names = self._manager.category_names
        self._category_combo.addItems(names)
        self._category_combo.blockSignals(False)
        if names:
            self._category_combo.setCurrentText(names[0])
            self._refresh_preset_list()

    def _refresh_preset_list(self):
        self._preset_list.clear()
        cat_name = self._category_combo.currentText()
        cat = self._manager.get_category(cat_name)
        if cat is None:
            return

        for preset in cat.presets:
            item = QtWidgets.QListWidgetItem()
            widget = PresetListItem(preset)
            item.setSizeHint(widget.sizeHint())
            self._preset_list.addItem(item)
            self._preset_list.setItemWidget(item, widget)

    # ── Category actions ─────────────────────────────────────────────

    def _on_category_changed(self, name: str):
        self._refresh_preset_list()

    def _on_add_category(self):
        name, ok = QtWidgets.QInputDialog.getText(
            self, self.tr("New Category"), self.tr("Category name:")
        )
        if ok and name.strip():
            self._manager.create_category(name.strip())
            self._populate_categories()
            self._category_combo.setCurrentText(name.strip())

    def _on_delete_category(self):
        cat_name = self._category_combo.currentText()
        if not cat_name:
            return
        reply = QtWidgets.QMessageBox.question(
            self,
            self.tr("Delete Category"),
            self.tr('Delete category "%s" and all its presets?') % cat_name,
            QtWidgets.QMessageBox.StandardButton.Yes
            | QtWidgets.QMessageBox.StandardButton.No,
        )
        if reply == QtWidgets.QMessageBox.StandardButton.Yes:
            self._manager.delete_category(cat_name)
            self._populate_categories()

    def _on_rename_category(self):
        old_name = self._category_combo.currentText()
        if not old_name:
            return
        new_name, ok = QtWidgets.QInputDialog.getText(
            self,
            self.tr("Rename Category"),
            self.tr("New name:"),
            text=old_name,
        )
        if ok and new_name.strip() and new_name.strip() != old_name:
            if self._manager.rename_category(old_name, new_name.strip()):
                self._populate_categories()
                self._category_combo.setCurrentText(new_name.strip())

    # ── Preset actions ───────────────────────────────────────────────

    def _on_preset_clicked(self, item: QtWidgets.QListWidgetItem):
        row = self._preset_list.row(item)
        cat_name = self._category_combo.currentText()
        cat = self._manager.get_category(cat_name)
        if cat and 0 <= row < len(cat.presets):
            self.preset_applied.emit(cat.presets[row])

    def _on_add_preset(self):
        name, ok = QtWidgets.QInputDialog.getText(
            self, self.tr("New Preset"), self.tr("Preset name:")
        )
        if ok and name.strip():
            self.capture_requested.emit(name.strip())

    def add_preset_entry(self, preset: ToolPreset):
        """Called by the controller after capturing current settings."""
        cat_name = self._category_combo.currentText()
        if not cat_name:
            cat_name = "Default"
        self._manager.add_preset(cat_name, preset)
        self._refresh_preset_list()

    def _on_delete_preset(self):
        row = self._preset_list.currentRow()
        if row < 0:
            return
        cat_name = self._category_combo.currentText()
        cat = self._manager.get_category(cat_name)
        if cat is None or row >= len(cat.presets):
            return

        preset_name = cat.presets[row].name
        reply = QtWidgets.QMessageBox.question(
            self,
            self.tr("Delete Preset"),
            self.tr('Delete preset "%s"?') % preset_name,
            QtWidgets.QMessageBox.StandardButton.Yes
            | QtWidgets.QMessageBox.StandardButton.No,
        )
        if reply == QtWidgets.QMessageBox.StandardButton.Yes:
            self._manager.remove_preset(cat_name, row)
            self._refresh_preset_list()

    def _on_import_fonts(self):
        file_paths, _ = QtWidgets.QFileDialog.getOpenFileNames(
            self,
            self.tr("Import Font Files"),
            "",
            self.tr("Font files (*.ttf *.ttc *.otf *.woff *.woff2)"),
        )
        if not file_paths:
            return

        cat_name = self._category_combo.currentText()
        if not cat_name:
            cat_name = "Default"

        # Copy files to user fonts dir and get base names
        results = self._manager.import_fonts_to_category(cat_name, file_paths)

        # Emit signal so the controller can load fonts into QFontDatabase
        # and create proper presets with resolved family names
        self.fonts_imported.emit(
            [(cat_name, file_paths, results)]
        )

    def finalize_font_import(
        self, category_name: str, font_entries: list[tuple[str, str]]
    ):
        """Called after controller resolves font families.

        *font_entries* is a list of ``(display_name, resolved_family)``.
        Creates a preset for each imported font.
        """
        for display_name, family_name in font_entries:
            preset = ToolPreset(
                name=f"{display_name} ({family_name})" if family_name != display_name else display_name,
                font_family=family_name,
            )
            self._manager.add_preset(category_name, preset)

        if self._category_combo.currentText() == category_name:
            self._refresh_preset_list()

    # ── Context menu ─────────────────────────────────────────────────

    def _show_context_menu(self, pos: QtCore.QPoint):
        item = self._preset_list.itemAt(pos)
        if item is None:
            return
        row = self._preset_list.row(item)
        cat_name = self._category_combo.currentText()
        cat = self._manager.get_category(cat_name)
        if cat is None or row >= len(cat.presets):
            return

        menu = QtWidgets.QMenu(self)

        rename_action = menu.addAction(self.tr("Rename"))
        update_action = menu.addAction(self.tr("Update with current settings"))
        menu.addSeparator()
        delete_action = menu.addAction(self.tr("Delete"))

        action = menu.exec(self._preset_list.mapToGlobal(pos))
        if action is None:
            return

        if action == rename_action:
            self._rename_preset(row, cat_name)
        elif action == update_action:
            self._update_preset(row)
        elif action == delete_action:
            self._manager.remove_preset(cat_name, row)
            self._refresh_preset_list()

    def _rename_preset(self, row: int, cat_name: str):
        cat = self._manager.get_category(cat_name)
        if cat is None or row >= len(cat.presets):
            return
        old_name = cat.presets[row].name
        new_name, ok = QtWidgets.QInputDialog.getText(
            self,
            self.tr("Rename Preset"),
            self.tr("New name:"),
            text=old_name,
        )
        if ok and new_name.strip():
            self._manager.rename_preset(cat_name, row, new_name.strip())
            self._refresh_preset_list()

    def _update_preset(self, row: int):
        """Request the controller to overwrite this preset with current settings."""
        cat_name = self._category_combo.currentText()
        cat = self._manager.get_category(cat_name)
        if cat is None or row >= len(cat.presets):
            return
        # Store the update target so the controller can find it
        self._pending_update_index = row
        self._pending_update_category = cat_name
        self.capture_requested.emit("")  # empty name = update mode

    def update_preset_entry(self, preset: ToolPreset):
        """Called by controller in update mode."""
        cat_name = getattr(self, "_pending_update_category", None)
        row = getattr(self, "_pending_update_index", -1)
        if cat_name is None or row < 0:
            return
        preset.name = self._manager.get_category(cat_name).presets[row].name
        self._manager.update_preset(cat_name, row, preset)
        self._refresh_preset_list()
        self._pending_update_category = None
        self._pending_update_index = -1

    # ── Public helpers ───────────────────────────────────────────────

    @property
    def manager(self) -> PresetManager:
        return self._manager
