from __future__ import annotations

import logging
import os

from PySide6.QtGui import QColor

from app.ui.canvas.text.text_item_properties import TextItemProperties
from app.ui.canvas.text_item import TextBlockItem
from app.ui.messages import Messages
from pipeline.render_state import set_target_snapshot, update_render_style_overrides

logger = logging.getLogger(__name__)


class TextBulkSupportMixin:
    def _get_image_state_for_path(self, file_path: str):
        state = self.main.image_states.get(file_path)
        if state is not None:
            return state
        target_norm = os.path.normcase(file_path)
        for key, value in self.main.image_states.items():
            if os.path.normcase(key) == target_norm:
                return value
        return None

    def _apply_bulk_text_update(self, per_page_fn=None, per_scene_fn=None, action_name: str = "bulk text update"):
        updated_any = False
        updated_pages = 0
        updated_files: list[str] = []
        for file_path in self.main.image_files:
            state = self._get_image_state_for_path(file_path)
            if state is None:
                continue
            if per_page_fn is not None:
                try:
                    if per_page_fn(file_path, state):
                        updated_any = True
                        updated_pages += 1
                        updated_files.append(file_path)
                except Exception:
                    continue

        if per_scene_fn is not None:
            try:
                if per_scene_fn():
                    updated_any = True
            except Exception:
                pass

        self._refresh_current_text_controls()

        if updated_any:
            current_target = self._current_target_lang()
            for file_path in updated_files:
                state = self.main.image_states.get(file_path)
                if state is not None and state.get("target_lang") == current_target:
                    set_target_snapshot(state, current_target, state.get("viewer_state", {}) or {})
                    update_render_style_overrides(state, state.get("viewer_state", {}) or {})
                self.main.stage_nav_ctrl.invalidate_for_format_edit(file_path, current_target)
            current_file = self._current_file_path()
            if current_file:
                self._sync_current_render_snapshot(current_file, update_style_overrides=True)
            self.main.mark_project_dirty()
            logger.info("%s applied to %d page(s).", action_name, updated_pages)
            self._show_bulk_update_message(action_name, updated_pages)

    def _capture_bulk_font_snapshot(self):
        snapshot = {}
        for file_path in self.main.image_files:
            state = self._get_image_state_for_path(file_path)
            if not state:
                continue
            text_items_state = state.get("viewer_state", {}).get("text_items_state", [])
            snapshot[file_path] = [
                {
                    "font_family": item_state.get("font_family", ""),
                    "line_spacing": item_state.get("line_spacing", 0),
                }
                if isinstance(item_state, dict)
                else {"font_family": "", "line_spacing": 0}
                for item_state in text_items_state
            ]

        current_path = self._current_file_path()
        current_items = []
        if self.main.image_viewer and self.main.image_viewer.text_items:
            current_items = [
                {
                    "font_family": getattr(item, "font_family", ""),
                    "line_spacing": getattr(item, "line_spacing", 0),
                }
                for item in self.main.image_viewer.text_items
            ]
        if current_path:
            snapshot[current_path] = current_items
        self._bulk_font_restore_snapshot = snapshot

    def _get_bulk_font_snapshot(self):
        snapshot = self._bulk_font_restore_snapshot or {}
        if not snapshot:
            return {}
        return snapshot

    @staticmethod
    def _normalize_bulk_font_snapshot_entry(entry):
        if isinstance(entry, dict):
            return {
                "font_family": entry.get("font_family", ""),
                "line_spacing": entry.get("line_spacing", 0),
            }
        if isinstance(entry, str):
            return {"font_family": entry, "line_spacing": 0}
        return {"font_family": "", "line_spacing": 0}

    def _show_bulk_update_message(self, action_name: str, updated_pages: int):
        if updated_pages <= 0:
            return
        try:
            Messages.show_bulk_text_update(self.main, action_name, updated_pages)
        except Exception:
            pass

    def _make_temp_text_item(self, props: TextItemProperties, font_family: str) -> TextBlockItem:
        render_color = props.text_color
        if render_color is None:
            selected_color = self.main.block_font_color_button.property("selected_color")
            render_color = QColor(selected_color) if selected_color else QColor("#000000")

        temp_width = props.width if props.width is not None and props.width > 0 else 1000
        temp_item = TextBlockItem(
            text=props.text,
            font_family=props.font_family,
            font_size=props.font_size,
            render_color=render_color,
            alignment=props.alignment,
            line_spacing=props.line_spacing,
            outline_color=props.outline_color,
            outline_width=props.outline_width,
            second_outline=props.second_outline,
            second_outline_color=props.second_outline_color,
            second_outline_width=props.second_outline_width,
            text_gradient=props.text_gradient,
            text_gradient_start_color=props.text_gradient_start_color,
            text_gradient_end_color=props.text_gradient_end_color,
            bold=props.bold,
            italic=props.italic,
            underline=props.underline,
            direction=props.direction,
        )
        temp_item.set_text(props.text, temp_width)
        temp_item.set_font(font_family, props.font_size)
        source_text = props.source_text or temp_item.get_source_text()
        if source_text:
            temp_item.set_source_text(source_text)
            temp_height = props.height if props.height is not None and props.height > 0 else temp_item.get_text_box_size()[1]
            temp_item.reflow_from_source_text(
                temp_width,
                temp_height,
                max_font_size=int(round(props.font_size)) if props.font_size else None,
            )
        return temp_item

    def _reflow_current_text_item(self, max_font_size: int | None = None):
        text_item = self.main.curr_tblock_item
        if not text_item:
            return
        width, height = text_item.get_text_box_size()
        text_item.reflow_from_source_text(width, height, max_font_size=max_font_size)

    def _get_saved_item_source_text(self, item_state: dict) -> str:
        source_text = item_state.get("source_text", "")
        if source_text:
            return source_text

        try:
            props = TextItemProperties.from_dict(item_state)
            temp_item = self._make_temp_text_item(props, props.font_family)
            return temp_item.get_source_text()
        except Exception:
            return item_state.get("text", "")

    def _rebuild_saved_item_layout(self, item_state: dict) -> bool:
        try:
            props = TextItemProperties.from_dict(item_state)
            temp_item = self._make_temp_text_item(props, props.font_family)
            item_state["text"] = temp_item.toHtml()
            item_state["source_text"] = temp_item.get_source_text()
            item_state["font_family"] = temp_item.font_family
            width, height = temp_item.get_text_box_size()
            item_state["width"] = width
            item_state["height"] = height
            return True
        except Exception:
            return False

    def _transform_text_item_html(
        self,
        html: str,
        item_state: dict | None = None,
        font_family: str | None = None,
        transform_font_fn=None,
        transform_case_fn=None,
    ) -> str:
        if not html:
            return html

        if transform_case_fn is not None:
            return transform_case_fn(html)

        if item_state is None or transform_font_fn is None:
            return html

        try:
            props = TextItemProperties.from_dict(item_state)
            temp_item = self._make_temp_text_item(props, font_family or props.font_family)
            return temp_item.toHtml()
        except Exception:
            return html

    def _update_saved_text_items(
        self,
        state,
        transform_text_fn=None,
        transform_font_fn=None,
        transform_source_text_fn=None,
    ) -> bool:
        updated = False
        text_items_state = state.setdefault("viewer_state", {}).get("text_items_state", [])

        for item_state in text_items_state:
            if not isinstance(item_state, dict):
                continue

            old_html = item_state.get("text", "")
            old_font_family = item_state.get("font_family") if transform_font_fn is not None else None
            old_source_text = item_state.get("source_text", "") if transform_source_text_fn is not None else None
            if transform_font_fn is not None:
                transform_font_fn(item_state)

            if transform_source_text_fn is not None:
                source_text = self._get_saved_item_source_text(item_state)
                transformed_source_text = transform_source_text_fn(source_text)
                if transformed_source_text != source_text:
                    item_state["source_text"] = transformed_source_text
                    updated = True

            if transform_text_fn is not None and old_html:
                new_html = transform_text_fn(old_html, item_state)
                if new_html != old_html:
                    item_state["text"] = new_html
                    updated = True

            if transform_font_fn is not None and old_font_family != item_state.get("font_family"):
                updated = True

            if transform_source_text_fn is not None and old_source_text != item_state.get("source_text"):
                updated = True

            if (transform_font_fn is not None or transform_source_text_fn is not None) and self._rebuild_saved_item_layout(item_state):
                updated = True

        return updated

    def _update_current_scene_text_items(
        self,
        transform_text_fn=None,
        transform_font_fn=None,
        transform_source_text_fn=None,
    ) -> bool:
        if not (self.main.image_viewer and self.main.image_viewer.text_items):
            return False

        updated = False
        for item in self.main.image_viewer.text_items:
            try:
                source_changed = False
                style_before = (
                    getattr(item, "font_family", ""),
                    getattr(item, "font_size", 0),
                    getattr(item, "bold", False),
                    getattr(item, "italic", False),
                    getattr(item, "underline", False),
                    getattr(item, "line_spacing", 0),
                )
                if transform_text_fn is not None:
                    html = item.toHtml()
                    transformed_html = transform_text_fn(html, item)
                    if transformed_html != html:
                        width = item.textWidth()
                        if width is None or width <= 0:
                            width = item.document().size().width()
                        item.set_text(transformed_html, width)
                        updated = True
                if transform_source_text_fn is not None and hasattr(item, "get_source_text"):
                    source_text = item.get_source_text()
                    transformed_source_text = transform_source_text_fn(source_text)
                    if transformed_source_text != source_text:
                        item.set_source_text(transformed_source_text)
                        source_changed = True
                if transform_font_fn is not None:
                    transform_font_fn(item)
                style_after = (
                    getattr(item, "font_family", ""),
                    getattr(item, "font_size", 0),
                    getattr(item, "bold", False),
                    getattr(item, "italic", False),
                    getattr(item, "underline", False),
                    getattr(item, "line_spacing", 0),
                )
                style_changed = style_after != style_before
                if style_changed:
                    updated = True
                if (source_changed or style_changed) and hasattr(item, "reflow_from_source_text"):
                    width, height = item.get_text_box_size()
                    item.reflow_from_source_text(
                        width,
                        height,
                        max_font_size=int(round(getattr(item, "font_size", 1))),
                    )
                    updated = True
            except Exception:
                continue
        return updated
