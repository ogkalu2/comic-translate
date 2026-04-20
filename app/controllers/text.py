from __future__ import annotations

from typing import TYPE_CHECKING

from PySide6 import QtCore

from app.controllers.text_bulk_font_mixin import TextBulkFontMixin
from app.controllers.text_bulk_style_mixin import TextBulkStyleMixin
from app.controllers.text_bulk_support_mixin import TextBulkSupportMixin
from app.controllers.text_format_mixin import TextFormatMixin
from app.controllers.text_render_mixin import TextRenderMixin
from app.controllers.text_scene_edit_mixin import TextSceneEditMixin
from app.controllers.text_scene_item_mixin import TextSceneItemMixin
from app.controllers.text_state_mixin import TextStateMixin

if TYPE_CHECKING:
    from controller import ComicTranslate


class TextController(
    TextStateMixin,
    TextSceneItemMixin,
    TextSceneEditMixin,
    TextBulkSupportMixin,
    TextBulkFontMixin,
    TextBulkStyleMixin,
    TextFormatMixin,
    TextRenderMixin,
):
    def __init__(self, main: ComicTranslate):
        self.main = main

        self.widgets_to_block = [
            self.main.font_dropdown,
            self.main.font_size_dropdown,
            self.main.line_spacing_dropdown,
            self.main.block_font_color_button,
            self.main.outline_font_color_button,
            self.main.outline_width_dropdown,
            self.main.outline_checkbox,
            self.main.text_gradient_checkbox,
            self.main.text_gradient_start_button,
            self.main.text_gradient_end_button,
            self.main.second_outline_checkbox,
            self.main.second_outline_color_button,
            self.main.second_outline_width_dropdown,
        ]
        self._text_change_timer = QtCore.QTimer(self.main)
        self._text_change_timer.setSingleShot(True)
        self._text_change_timer.setInterval(400)
        self._text_change_timer.timeout.connect(self._commit_pending_text_command)
        self._pending_text_command = None
        self._last_item_text = {}
        self._last_item_html = {}
        self._suspend_text_command = False
        self._is_updating_from_edit = False
        self._bulk_font_restore_snapshot = None
        self._manual_render_macro_open = False
        self._last_target_lang = ""
