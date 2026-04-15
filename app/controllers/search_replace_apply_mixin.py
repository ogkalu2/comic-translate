from __future__ import annotations

import copy

from PySide6 import QtCore, QtGui

from app.controllers.search_replace_core import (
    BlockKey,
    SearchOptions,
    _apply_replacements_to_html,
    _apply_text_delta_to_document,
    _looks_like_html,
    build_block_key,
    compile_search_pattern,
    find_block_by_key,
    find_matching_text_item_state,
    replace_all_matches,
    replace_nth_match,
)
from modules.utils.common_utils import is_close


class SearchReplaceApplyMixin:
    def _apply_block_text(self, opts: SearchOptions, key: BlockKey, new_text: str):
        return self._apply_block_text_with_html(opts, key, new_text, html_override=None)

    def _find_matching_text_item_state(self, state: dict, key: BlockKey) -> dict | None:
        return find_matching_text_item_state(state, key)

    def _apply_block_text_with_html(
        self, opts: SearchOptions, key: BlockKey, new_text: str, *, html_override: str | None
    ):
        state = self.main.image_states.get(key.file_path)
        if state:
            saved_blk = find_block_by_key(state.get("blk_list") or [], key)
            if saved_blk is not None:
                if opts.in_target:
                    saved_blk.translation = new_text
                else:
                    saved_blk.text = new_text

            if opts.in_target:
                text_item_state = self._find_matching_text_item_state(state, key)
                if text_item_state is not None:
                    if html_override is not None:
                        text_item_state["text"] = html_override
                    else:
                        existing = text_item_state.get("text") or ""
                        if _looks_like_html(existing):
                            try:
                                doc = QtGui.QTextDocument()
                                doc.setHtml(existing)
                                if _apply_text_delta_to_document(doc, new_text):
                                    text_item_state["text"] = doc.toHtml()
                            except Exception:
                                pass
                        else:
                            text_item_state["text"] = new_text

        blk = self._find_block_in_current_image(key)
        if blk is None:
            return

        if opts.in_target:
            blk.translation = new_text
        else:
            blk.text = new_text

        if opts.in_target:
            try:
                for text_item in self.main.image_viewer.text_items:
                    x = float(text_item.pos().x())
                    y = float(text_item.pos().y())
                    rot = float(text_item.rotation())
                    if is_close(x, key.xyxy[0], 5) and is_close(y, key.xyxy[1], 5) and is_close(rot, key.angle, 1.0):
                        if html_override is not None:
                            self.main.text_ctrl.apply_text_from_command(text_item, new_text, html=html_override, blk=blk)
                        else:
                            html = None
                            try:
                                existing = text_item.document().toHtml()
                                if _looks_like_html(existing):
                                    doc = QtGui.QTextDocument()
                                    doc.setHtml(existing)
                                    if _apply_text_delta_to_document(doc, new_text):
                                        html = doc.toHtml()
                            except Exception:
                                html = None
                            self.main.text_ctrl.apply_text_from_command(text_item, new_text, html=html, blk=blk)
                        break
            except Exception:
                pass

        try:
            if self.main.curr_tblock is blk:
                if opts.in_target:
                    self.main.t_text_edit.blockSignals(True)
                    self.main.t_text_edit.setPlainText(new_text)
                    self.main.t_text_edit.blockSignals(False)
                else:
                    self.main.s_text_edit.blockSignals(True)
                    self.main.s_text_edit.setPlainText(new_text)
                    self.main.s_text_edit.blockSignals(False)
        except Exception:
            pass

        target_lang = ""
        if state:
            target_lang = state.get("target_lang", "") or self.main.t_combo.currentText()
            if opts.in_target:
                target_render_states = state.setdefault("target_render_states", {})
                if target_lang and state.get("viewer_state"):
                    target_render_states[target_lang] = copy.deepcopy(state.get("viewer_state", {}) or {})

        if opts.in_target:
            try:
                if key.file_path == self.main.image_files[self.main.curr_img_idx]:
                    self.main.text_ctrl._sync_current_render_snapshot(key.file_path)
            except Exception:
                pass
            self.main.stage_nav_ctrl.invalidate_for_translated_text_edit(
                key.file_path,
                target_lang or self.main.t_combo.currentText(),
            )
        else:
            self.main.stage_nav_ctrl.invalidate_for_source_text_edit(key.file_path)

        try:
            self.main.mark_project_dirty()
        except Exception:
            pass

    def _apply_block_text_by_key(
        self,
        *,
        in_target: bool,
        file_path: str,
        xyxy: tuple[int, int, int, int],
        angle: float,
        new_text: str,
        html_override: str | None = None,
    ):
        key = BlockKey(file_path=file_path, xyxy=xyxy, angle=angle)
        opts = SearchOptions(query="", replace="", in_target=bool(in_target))
        self._apply_block_text_with_html(opts, key, new_text, html_override=html_override)

    def replace_current(self):
        if not self._matches or self._active_match_index < 0:
            return
        panel = self.main.search_panel
        opts = self._gather_options()
        try:
            pattern = compile_search_pattern(opts)
        except Exception as err:
            panel.set_status(
                QtCore.QCoreApplication.translate("SearchReplaceController", "Replace Error")
                + ": "
                + self._format_pattern_error(err)
            )
            return

        match = self._matches[self._active_match_index]
        state = self.main.image_states.get(match.key.file_path) or {}
        new_html = None
        old_text = None
        new_text = None

        if opts.in_target:
            text_item_state = self._find_matching_text_item_state(state, match.key)
            existing_html = (text_item_state.get("text") if text_item_state else None) if isinstance(text_item_state, dict) else None
            if isinstance(existing_html, str) and _looks_like_html(existing_html):
                old_text, new_text, new_html, count = _apply_replacements_to_html(
                    existing_html,
                    pattern,
                    opts.replace,
                    regex_mode=opts.regex,
                    preserve_case=opts.preserve_case,
                    nth=match.match_ordinal_in_block,
                )
                if count <= 0 or new_text == old_text:
                    return

        if old_text is None:
            target_blk = self._find_block_in_current_image(match.key)
            if target_blk is None:
                target_blk = find_block_by_key(state.get("blk_list") or [], match.key)
            if target_blk is None:
                return
            old_text = target_blk.translation if opts.in_target else target_blk.text
            new_text, changed = replace_nth_match(
                old_text,
                pattern,
                opts.replace,
                match.match_ordinal_in_block,
                regex_mode=opts.regex,
            )
            if not changed or new_text == old_text:
                return

        self._apply_block_text_with_html(opts, match.key, new_text, html_override=new_html)
        panel.set_status(QtCore.QCoreApplication.translate("SearchReplaceController", "Replaced 1 occurrence(s)"))
        self.search()

    def replace_all(self):
        panel = self.main.search_panel
        opts = self._gather_options()
        try:
            pattern = compile_search_pattern(opts)
        except Exception as err:
            panel.set_status(
                QtCore.QCoreApplication.translate("SearchReplaceController", "Replace Error")
                + ": "
                + self._format_pattern_error(err)
            )
            return

        total_replacements = 0
        for file_path, _blk_list, _idx, blk in self._iter_blocks(opts) or []:
            key = build_block_key(file_path, blk)
            state = self.main.image_states.get(file_path) or {}
            new_html = None

            if opts.in_target:
                text_item_state = self._find_matching_text_item_state(state, key)
                existing_html = (text_item_state.get("text") if text_item_state else None) if isinstance(text_item_state, dict) else None
                if isinstance(existing_html, str) and _looks_like_html(existing_html):
                    old_text, new_text, new_html, count = _apply_replacements_to_html(
                        existing_html,
                        pattern,
                        opts.replace,
                        regex_mode=opts.regex,
                        preserve_case=opts.preserve_case,
                        nth=None,
                    )
                    if count <= 0 or new_text == old_text:
                        continue
                else:
                    old_text = blk.translation
                    new_text, count = replace_all_matches(
                        old_text,
                        pattern,
                        opts.replace,
                        regex_mode=opts.regex,
                        preserve_case=opts.preserve_case,
                    )
                    if count <= 0 or new_text == old_text:
                        continue
            else:
                old_text = blk.text
                new_text, count = replace_all_matches(
                    old_text,
                    pattern,
                    opts.replace,
                    regex_mode=opts.regex,
                    preserve_case=opts.preserve_case,
                )
                if count <= 0 or new_text == old_text:
                    continue

            total_replacements += count
            self._apply_block_text_with_html(opts, key, new_text, html_override=new_html)

        if total_replacements:
            panel.set_status(
                QtCore.QCoreApplication.translate("SearchReplaceController", "Replaced {0} occurrence(s)").format(total_replacements)
            )
        else:
            panel.set_status(QtCore.QCoreApplication.translate("SearchReplaceController", "No replacements"))
        self.search()
