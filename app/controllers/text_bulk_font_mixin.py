from __future__ import annotations

from app.ui.messages import Messages


class TextBulkFontMixin:
    def apply_font_to_all_pages(self):
        font_family = self.main.font_dropdown.currentText()
        if not font_family:
            return

        try:
            line_spacing = float(self.main.line_spacing_dropdown.currentText())
        except Exception:
            line_spacing = None

        self._capture_bulk_font_snapshot()

        def _set_item_font(item_or_state):
            if isinstance(item_or_state, dict):
                item_or_state["font_family"] = font_family
                if line_spacing is not None:
                    item_or_state["line_spacing"] = line_spacing
            else:
                item_or_state.set_font(font_family, item_or_state.font_size)
                if line_spacing is not None:
                    item_or_state.set_line_spacing(line_spacing)

        def _transform_saved_html(old_html, item_state):
            return self._transform_text_item_html(
                old_html,
                item_state=item_state,
                font_family=font_family,
                transform_font_fn=_set_item_font,
            )

        def _update_page(_file_path, state):
            return self._update_saved_text_items(
                state,
                transform_text_fn=_transform_saved_html,
                transform_font_fn=_set_item_font,
            )

        def _update_scene():
            return self._update_current_scene_text_items(
                transform_font_fn=_set_item_font,
            )

        self._apply_bulk_text_update(
            _update_page,
            _update_scene,
            action_name=Messages.bulk_apply_font_all_label(),
        )

    def restore_font_to_all_pages(self):
        snapshot = self._get_bulk_font_snapshot()
        if not snapshot:
            return

        def _update_page(file_path, state):
            page_snapshot = snapshot.get(file_path, [])
            if not page_snapshot:
                return False

            text_items_state = state.get("viewer_state", {}).get("text_items_state", [])
            updated = False
            for idx, item_state in enumerate(text_items_state):
                if not isinstance(item_state, dict):
                    continue
                prev_state = self._normalize_bulk_font_snapshot_entry(
                    page_snapshot[idx] if idx < len(page_snapshot) else {}
                )
                font_family = prev_state.get("font_family", "")
                line_spacing = prev_state.get("line_spacing", 0)
                if font_family and item_state.get("font_family") != font_family:
                    item_state["font_family"] = font_family
                    updated = True
                if item_state.get("line_spacing", 0) != line_spacing:
                    item_state["line_spacing"] = line_spacing
                    updated = True
                    self._rebuild_saved_item_layout(item_state)
            return updated

        def _update_scene():
            current_path = self._current_file_path()
            page_snapshot = snapshot.get(current_path, [])
            if not page_snapshot or not self.main.image_viewer.text_items:
                return False

            updated = False
            for idx, item in enumerate(self.main.image_viewer.text_items):
                prev_state = self._normalize_bulk_font_snapshot_entry(
                    page_snapshot[idx] if idx < len(page_snapshot) else {}
                )
                font_family = prev_state.get("font_family", "")
                line_spacing = prev_state.get("line_spacing", 0)
                if font_family and getattr(item, "font_family", "") != font_family:
                    item.set_font(font_family, item.font_size)
                    updated = True
                if line_spacing is not None and getattr(item, "line_spacing", 0) != line_spacing:
                    item.set_line_spacing(line_spacing)
                    updated = True
                if font_family or line_spacing is not None:
                    width, height = item.get_text_box_size()
                    item.reflow_from_source_text(
                        width,
                        height,
                        max_font_size=int(round(getattr(item, "font_size", 1))),
                    )
                    updated = True
            return updated

        self._apply_bulk_text_update(
            _update_page,
            _update_scene,
            action_name=Messages.bulk_restore_font_all_label(),
        )
