"""Controller for Tool Presets feature.

Handles the bridge between the PresetPanel UI and the main application
toolbar widgets. Responsible for:
- Applying a preset (setting all toolbar widgets + updating selected text items)
- Capturing current toolbar state into a new preset
- Importing fonts and creating presets from imported files
"""

from __future__ import annotations

import copy
import logging
import os
from typing import TYPE_CHECKING

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QFontDatabase

from app.ui.preset_model import ToolPreset
from app.ui.commands.textformat import TextFormatCommand
from modules.utils.paths import get_user_data_dir

if TYPE_CHECKING:
    from controller import ComicTranslate

logger = logging.getLogger(__name__)


class PresetController:
    """Manages applying / capturing tool presets."""

    def __init__(self, main: ComicTranslate):
        self.main = main

    # ── Apply preset ─────────────────────────────────────────────────

    def apply_preset(self, preset: ToolPreset) -> None:
        """Apply all properties from *preset* to the toolbar widgets.

        If text items are currently selected, the formatting is also
        applied to them via the undo/redo command system.
        """
        logger.info("Applying preset: %s", preset.name)

        # Block signals from all text widgets to prevent cascading updates
        widgets = self.main.text_ctrl.widgets_to_block
        self.main.text_ctrl.block_text_item_widgets(widgets)

        try:
            # Font family
            resolved = self.main.ensure_custom_font_loaded(preset.font_family)
            self.main.set_font(resolved)

            # Font size
            self.main.font_size_dropdown.setCurrentText(str(preset.font_size))

            # Line spacing
            self.main.line_spacing_dropdown.setCurrentText(str(preset.line_spacing))

            # Font color
            self.main.block_font_color_button.setStyleSheet(
                f"background-color: {preset.color}; border: none; border-radius: 5px;"
            )
            self.main.block_font_color_button.setProperty("selected_color", preset.color)

            # Bold / Italic / Underline
            self.main.bold_button.setChecked(preset.bold)
            self.main.italic_button.setChecked(preset.italic)
            self.main.underline_button.setChecked(preset.underline)

            # Alignment
            alignment_index = max(0, min(2, preset.alignment))
            self.main.alignment_tool_group.set_dayu_checked(alignment_index)

            # Outline
            self.main.outline_checkbox.setChecked(preset.outline)
            self.main.outline_font_color_button.setStyleSheet(
                f"background-color: {preset.outline_color}; border: none; border-radius: 5px;"
            )
            self.main.outline_font_color_button.setProperty(
                "selected_color", preset.outline_color
            )
            self.main.outline_width_dropdown.setCurrentText(str(preset.outline_width))

        finally:
            self.main.text_ctrl.unblock_text_item_widgets(widgets)

        # Apply to selected text items if any
        self._apply_to_selected_items(preset)

    def _apply_to_selected_items(self, preset: ToolPreset) -> None:
        """Apply the preset to all currently selected text items."""
        items = self.main.text_ctrl._selected_text_items()
        if not items:
            return

        alignment_map = {
            0: Qt.AlignmentFlag.AlignLeft,
            1: Qt.AlignmentFlag.AlignCenter,
            2: Qt.AlignmentFlag.AlignRight,
        }
        alignment = alignment_map.get(preset.alignment, Qt.AlignmentFlag.AlignCenter)

        outline_color = QColor(preset.outline_color) if preset.outline else None
        outline_width = preset.outline_width if preset.outline else 0.0

        commands = []
        for item in items:
            old_item = copy.copy(item)

            # Apply all properties
            resolved = self.main.ensure_custom_font_loaded(preset.font_family)
            item.set_font(resolved, preset.font_size)
            item.set_color(QColor(preset.color))
            item.set_bold(preset.bold)
            item.set_italic(preset.italic)
            item.set_underline(preset.underline)
            item.set_alignment(alignment)
            item.set_line_spacing(preset.line_spacing)
            if preset.outline:
                item.set_outline(QColor(preset.outline_color), preset.outline_width)
            else:
                item.set_outline(None, None)

            commands.append(
                TextFormatCommand(self.main.image_viewer, old_item, item)
            )

        stack = self.main.undo_group.activeStack()
        if stack is None:
            return

        if len(commands) > 1:
            stack.beginMacro("apply_preset")
        try:
            for command in commands:
                stack.push(command)
        finally:
            if len(commands) > 1:
                stack.endMacro()

        # Sync toolbar with the (now applied) item
        if self.main.curr_tblock_item in items:
            self.main.text_ctrl.set_values_for_blk_item(self.main.curr_tblock_item)

    # ── Capture current state ────────────────────────────────────────

    def capture_current_as_preset(self, name: str) -> ToolPreset:
        """Read all current toolbar values and build a ToolPreset."""
        alignment_id = self.main.alignment_tool_group.get_dayu_checked()

        preset = ToolPreset(
            name=name,
            font_family=self.main.font_dropdown.currentText(),
            font_size=int(self.main.font_size_dropdown.currentText() or "12"),
            bold=self.main.bold_button.isChecked(),
            italic=self.main.italic_button.isChecked(),
            underline=self.main.underline_button.isChecked(),
            line_spacing=float(self.main.line_spacing_dropdown.currentText() or "1.0"),
            color=self.main.block_font_color_button.property("selected_color") or "#000000",
            outline=self.main.outline_checkbox.isChecked(),
            outline_color=self.main.outline_font_color_button.property("selected_color") or "#ffffff",
            outline_width=float(self.main.outline_width_dropdown.currentText() or "1.0"),
            alignment=alignment_id,
        )
        logger.info("Captured preset: %s", preset.name)
        return preset

    # ── Handle preset panel signals ──────────────────────────────────

    def on_capture_requested(self, name: str) -> None:
        """Connected to PresetPanel.capture_requested signal."""
        panel = self.main.preset_panel
        if not name:
            # Update mode
            preset = self.capture_current_as_preset("")
            panel.update_preset_entry(preset)
        else:
            # New preset  mode
            preset = self.capture_current_as_preset(name)
            panel.add_preset_entry(preset)

    def on_fonts_imported(self, payload: list) -> None:
        """Connected to PresetPanel.fonts_imported signal.

        *payload* is ``[(category_name, file_paths, results)]`` where
        *results* is from ``PresetManager.import_fonts_to_category``.
        """
        if not payload:
            return

        for cat_name, file_paths, results in payload:
            resolved_entries: list[tuple[str, str]] = []

            for basename, display_name in results:
                # Load the font into QFontDatabase
                fonts_dir = os.path.join(get_user_data_dir(), "fonts")
                full_path = os.path.join(fonts_dir, basename)
                family = self.main._load_custom_font_file(full_path)
                if family:
                    resolved_entries.append((display_name, family))
                else:
                    resolved_entries.append((display_name, display_name))

            panel = self.main.preset_panel
            panel.finalize_font_import(cat_name, resolved_entries)
