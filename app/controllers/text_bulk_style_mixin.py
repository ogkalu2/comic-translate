from __future__ import annotations

from app.ui.messages import Messages
from modules.utils.translator_utils import transform_text_case_preserving_html


class TextBulkStyleMixin:
    def _apply_boolean_style_to_all_pages(
        self,
        *,
        state_key: str,
        setter_name: str,
        value: bool,
        action_name: str,
    ) -> None:
        def _set_item_style(item_or_state):
            if isinstance(item_or_state, dict):
                item_or_state[state_key] = value
            else:
                getattr(item_or_state, setter_name)(value)

        def _update_page(_file_path, state):
            return self._update_saved_text_items(
                state,
                transform_font_fn=_set_item_style,
            )

        def _update_scene():
            return self._update_current_scene_text_items(
                transform_font_fn=_set_item_style,
            )

        self._apply_bulk_text_update(
            _update_page,
            _update_scene,
            action_name=action_name,
        )

    def apply_italic_to_all_pages(self):
        self._apply_boolean_style_to_all_pages(
            state_key="italic",
            setter_name="set_italic",
            value=True,
            action_name=Messages.bulk_italic_all_label(),
        )

    def apply_italic_off_to_all_pages(self):
        self._apply_boolean_style_to_all_pages(
            state_key="italic",
            setter_name="set_italic",
            value=False,
            action_name=Messages.bulk_italic_off_all_label(),
        )

    def apply_bold_to_all_pages(self):
        self._apply_boolean_style_to_all_pages(
            state_key="bold",
            setter_name="set_bold",
            value=True,
            action_name=Messages.bulk_bold_all_label(),
        )

    def apply_bold_off_to_all_pages(self):
        self._apply_boolean_style_to_all_pages(
            state_key="bold",
            setter_name="set_bold",
            value=False,
            action_name=Messages.bulk_bold_off_all_label(),
        )

    def apply_underline_to_all_pages(self):
        self._apply_boolean_style_to_all_pages(
            state_key="underline",
            setter_name="set_underline",
            value=True,
            action_name=Messages.bulk_underline_all_label(),
        )

    def apply_underline_off_to_all_pages(self):
        self._apply_boolean_style_to_all_pages(
            state_key="underline",
            setter_name="set_underline",
            value=False,
            action_name=Messages.bulk_underline_off_all_label(),
        )

    def apply_text_case_to_all_pages(self, upper_case: bool):
        def _transform_case_text(text: str) -> str:
            return text.upper() if upper_case else text.lower()

        def _transform_case_html(text: str) -> str:
            return transform_text_case_preserving_html(text, upper_case=upper_case)

        def _transform_saved_html(old_html, _item_state):
            return self._transform_text_item_html(
                old_html,
                transform_case_fn=_transform_case_html,
            )

        action_name = (
            Messages.bulk_upper_all_label()
            if upper_case
            else Messages.bulk_lower_all_label()
        )

        def _update_page(_file_path, state):
            updated = False
            for blk in state.get("blk_list", []):
                translation = getattr(blk, "translation", "")
                if not translation:
                    continue
                transformed_translation = translation.upper() if upper_case else translation.lower()
                if transformed_translation != translation:
                    blk.translation = transformed_translation
                    updated = True

            if self._update_saved_text_items(
                state,
                transform_text_fn=_transform_saved_html,
                transform_source_text_fn=_transform_case_text,
            ):
                updated = True
            return updated

        def _update_scene():
            return self._update_current_scene_text_items(
                transform_text_fn=_transform_saved_html,
                transform_source_text_fn=_transform_case_text,
            )

        self._apply_bulk_text_update(
            _update_page,
            _update_scene,
            action_name=action_name,
        )

    def handle_bulk_text_action_change(self, index: int):
        dropdown = self.main.bulk_text_action_dropdown
        if not dropdown or index <= 0:
            return

        action = dropdown.itemData(index)
        try:
            if action == "apply_font_all":
                self.apply_font_to_all_pages()
            elif action == "restore_font_all":
                self.restore_font_to_all_pages()
            elif action == "upper_all":
                self.apply_text_case_to_all_pages(True)
            elif action == "lower_all":
                self.apply_text_case_to_all_pages(False)
            elif action == "bold_all":
                self.apply_bold_to_all_pages()
            elif action == "bold_off_all":
                self.apply_bold_off_to_all_pages()
            elif action == "italic_all":
                self.apply_italic_to_all_pages()
            elif action == "italic_off_all":
                self.apply_italic_off_to_all_pages()
            elif action == "underline_all":
                self.apply_underline_to_all_pages()
            elif action == "underline_off_all":
                self.apply_underline_off_to_all_pages()
        finally:
            dropdown.blockSignals(True)
            dropdown.setCurrentIndex(0)
            dropdown.blockSignals(False)
