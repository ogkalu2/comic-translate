from __future__ import annotations

from typing import Iterator, TYPE_CHECKING

from PySide6 import QtCore, QtGui

from app.controllers.search_replace_apply_mixin import SearchReplaceApplyMixin
from app.controllers.search_replace_core import (
    SearchMatch,
    SearchOptions,
    _make_preview,
    build_block_key,
    compile_search_pattern,
    find_matches_in_text,
)
from app.controllers.search_replace_jump_mixin import SearchReplaceJumpMixin
from app.controllers.search_replace_selection_mixin import SearchReplaceSelectionMixin
if TYPE_CHECKING:
    from controller import ComicTranslate


class SearchReplaceController(
    SearchReplaceApplyMixin,
    SearchReplaceSelectionMixin,
    SearchReplaceJumpMixin,
    QtCore.QObject,
):
    def __init__(self, main: ComicTranslate):
        super().__init__(main)
        self.main = main
        self._matches: list[SearchMatch] = []
        self._active_match_index: int = -1
        self._shortcuts: list[QtGui.QShortcut] = []
        self._jump_nonce: int = 0

        panel = getattr(self.main, "search_panel", None)
        if panel is None:
            return

        panel.search_requested.connect(self.search)
        panel.next_requested.connect(self.next_match)
        panel.prev_requested.connect(self.prev_match)
        panel.replace_requested.connect(self.replace_current)
        panel.replace_all_requested.connect(self.replace_all)
        panel.result_activated.connect(self._on_result_activated)

        # Shortcuts (global to main window)
        QtGui.QShortcut(QtGui.QKeySequence.Find, self.main, activated=self.focus_find)
        QtGui.QShortcut(QtGui.QKeySequence.Replace, self.main, activated=self.focus_replace)

        # Enter in find input goes to next match, Ctrl+Enter for previous match
        panel.find_input.returnPressed.connect(self.next_match)
        self._shortcuts.append(
            QtGui.QShortcut(QtGui.QKeySequence("Ctrl+Return"), panel, activated=self.prev_match)
        )

        # Clear (Esc) when any widget in the panel has focus.
        clear_sc = QtGui.QShortcut(QtGui.QKeySequence(QtCore.Qt.Key.Key_Escape), panel, activated=panel._clear_find)
        clear_sc.setContext(QtCore.Qt.ShortcutContext.WidgetWithChildrenShortcut)
        self._shortcuts.append(clear_sc)

    def focus_find(self):
        if hasattr(self.main, "show_search_sidebar"):
            self.main.show_search_sidebar(focus="find")
            return
        panel = self.main.search_panel
        panel.find_input.setFocus()
        panel.find_input.selectAll()

    def focus_replace(self):
        if hasattr(self.main, "show_search_sidebar"):
            self.main.show_search_sidebar(focus="replace")
            return
        panel = self.main.search_panel
        panel.replace_input.setFocus()
        panel.replace_input.selectAll()

    def _capture_focus_state(self):
        try:
            w = self.main.focusWidget()
        except Exception:
            return None
        if w is None:
            return None
        # Only preserve QLineEdit-like widgets (MLineEdit is a QLineEdit subclass).
        if hasattr(w, "cursorPosition") and hasattr(w, "selectionStart") and hasattr(w, "selectedText"):
            try:
                sel_start = int(w.selectionStart())
                sel_len = len(w.selectedText() or "") if sel_start >= 0 else 0
                return {
                    "widget": w,
                    "cursor_pos": int(w.cursorPosition()),
                    "sel_start": sel_start,
                    "sel_len": sel_len,
                }
            except Exception:
                return {"widget": w}
        return None

    def _restore_focus_state(self, state):
        if not state:
            return
        w = state.get("widget")
        if w is None:
            return
        try:
            if not w.isVisible():
                return
        except Exception:
            pass

        def _apply():
            try:
                w.setFocus()
            except Exception:
                return
            try:
                sel_start = state.get("sel_start", -1)
                sel_len = state.get("sel_len", 0)
                cursor_pos = state.get("cursor_pos", None)
                if sel_start is not None and sel_start >= 0 and sel_len:
                    w.setSelection(sel_start, sel_len)
                elif cursor_pos is not None and hasattr(w, "setCursorPosition"):
                    w.setCursorPosition(int(cursor_pos))
            except Exception:
                pass

        # Defer to ensure we win against any focus changes from selection/jump logic.
        QtCore.QTimer.singleShot(0, _apply)

    def _gather_options(self) -> SearchOptions:
        panel = self.main.search_panel
        return SearchOptions(
            query=panel.find_input.text(),
            replace=panel.replace_input.text(),
            match_case=panel.match_case_btn.isChecked(),
            whole_word=panel.whole_word_btn.isChecked(),
            regex=panel.regex_btn.isChecked(),
            preserve_case=panel.preserve_case_btn.isChecked(),
            scope_all_images=(panel.scope_combo.currentData() == "all"),
            in_target=(panel.field_combo.currentData() == "target"),
        )

    def _format_pattern_error(self, err: Exception) -> str:
        """
        Map common validation errors to localized strings.
        """
        msg = str(err) if err is not None else ""
        if isinstance(err, ValueError) and msg == "Empty query":
            return QtCore.QCoreApplication.translate("SearchReplaceController", "Empty query")
        return msg

    def on_undo_redo(self, *_args):
        """Refresh search results after undo/redo without jumping/focusing."""
        panel = getattr(self.main, "search_panel", None)
        if panel is None:
            return
        if not (panel.find_input.text() or "").strip():
            return
        self.search(jump_to_first=False)

    def _iter_blocks(self, opts: SearchOptions) -> Iterator[tuple[str, list, int, object]]:
        """
        Yields (file_path, blk_list, index, blk) for the requested scope.
        """
        if not self.main.image_files:
            return

        if not opts.scope_all_images:
            # Webtoon mode "Current image" means visible area.
            if getattr(self.main, "webtoon_mode", False):
                viewer = getattr(self.main, "image_viewer", None)
                webtoon_manager = getattr(viewer, "webtoon_manager", None) if viewer is not None else None
                layout_manager = getattr(webtoon_manager, "layout_manager", None) if webtoon_manager is not None else None
                if layout_manager is not None:
                    try:
                        visible_pages = set()
                        # Use get_pages_for_scene_bounds with actual viewport rect (no buffer)
                        if (
                            viewer is not None
                            and hasattr(layout_manager, "get_pages_for_scene_bounds")
                            and hasattr(viewer, "viewport")
                            and viewer.viewport() is not None
                        ):
                            viewport_rect = viewer.mapToScene(viewer.viewport().rect()).boundingRect()
                            visible_pages |= set(layout_manager.get_pages_for_scene_bounds(viewport_rect) or set())
                        elif hasattr(layout_manager, "get_visible_pages"):
                            # Fallback to get_visible_pages (includes buffer, but better than nothing)
                            visible_pages |= set(layout_manager.get_visible_pages() or set())
                    except Exception:
                        visible_pages = set()

                    # If we can't determine visibility, fall back to current page.
                    if not visible_pages and self.main.curr_img_idx >= 0:
                        visible_pages = {self.main.curr_img_idx}

                    for page_idx in sorted(visible_pages):
                        if not (0 <= page_idx < len(self.main.image_files)):
                            continue
                        file_path = self.main.image_files[page_idx]
                        state = self.main.image_states.get(file_path) or {}
                        blks = state.get("blk_list") or []
                        for idx, blk in enumerate(blks):
                            yield file_path, blks, idx, blk
                    return

            if self.main.curr_img_idx < 0:
                return
            file_path = self.main.image_files[self.main.curr_img_idx]
            for idx, blk in enumerate(self.main.blk_list or []):
                yield file_path, self.main.blk_list, idx, blk
            return

        # Ensure current image edits are persisted into image_states.viewer_state when possible.
        # In webtoon mode, blocks are managed differently via the scene item manager,
        # so skip this to avoid incorrectly assigning all visible blocks to a single file.
        if not getattr(self.main, "webtoon_mode", False):
            try:
                self.main.image_ctrl.save_current_image_state()
            except Exception:
                pass

        for file_path in self.main.image_files:
            state = self.main.image_states.get(file_path) or {}
            blks = state.get("blk_list") or []
            for idx, blk in enumerate(blks):
                yield file_path, blks, idx, blk

    def search(self, jump_to_first: bool = True):
        panel = self.main.search_panel
        opts = self._gather_options()
        focus_state = self._capture_focus_state()
        prev_match = None
        if 0 <= self._active_match_index < len(self._matches):
            prev_match = self._matches[self._active_match_index]
        try:
            pattern = compile_search_pattern(opts)
        except Exception as e:
            panel.set_status(QtCore.QCoreApplication.translate('SearchReplaceController', 'Search Error') + ": " + self._format_pattern_error(e))
            panel.set_results([], 0, 0)
            self._matches = []
            self._active_match_index = -1
            return

        matches: list[SearchMatch] = []
        images_with_hits: set[str] = set()

        for file_path, _blk_list, idx, blk in self._iter_blocks(opts) or []:
            text = blk.translation if opts.in_target else blk.text
            spans = find_matches_in_text(text, pattern)
            if not spans:
                continue
            images_with_hits.add(file_path)
            for ordinal, (start, end) in enumerate(spans):
                key = build_block_key(file_path, blk)
                matches.append(
                    SearchMatch(
                        key=key,
                        block_index_hint=idx,
                        match_ordinal_in_block=ordinal,
                        start=start,
                        end=end,
                        preview=_make_preview(text, start, end),
                    )
                )

        self._matches = matches
        if matches:
            if prev_match is not None:
                try:
                    self._active_match_index = next(
                        i
                        for i, mm in enumerate(matches)
                        if mm.key == prev_match.key
                        and mm.match_ordinal_in_block == prev_match.match_ordinal_in_block
                        and mm.start == prev_match.start
                        and mm.end == prev_match.end
                    )
                except StopIteration:
                    self._active_match_index = 0
            else:
                self._active_match_index = 0
        else:
            self._active_match_index = -1

        panel.set_results(matches, len(images_with_hits), len(matches))
        if matches:
            panel.set_status(QtCore.QCoreApplication.translate("SearchReplaceController", "Ready"))
            if jump_to_first:
                # Avoid stealing keyboard focus from the find/replace inputs while typing.
                focus_editor = not (panel.find_input.hasFocus() or panel.replace_input.hasFocus())
                self._jump_to_match(
                    self._active_match_index if self._active_match_index >= 0 else 0,
                    focus=focus_editor,
                    preserve_focus_state=focus_state if not focus_editor else None,
                )
            else:
                if self._active_match_index >= 0:
                    panel.select_match(matches[self._active_match_index])
        else:
            panel.set_status(QtCore.QCoreApplication.translate("SearchReplaceController", "No results"))

    def next_match(self):
        if not self._matches:
            return
        self._active_match_index = (self._active_match_index + 1) % len(self._matches)
        panel = self.main.search_panel
        focus_state = self._capture_focus_state()
        focus_editor = not (panel.find_input.hasFocus() or panel.replace_input.hasFocus())
        self._jump_to_match(
            self._active_match_index, focus=focus_editor, preserve_focus_state=focus_state if not focus_editor else None
        )

    def prev_match(self):
        if not self._matches:
            return
        self._active_match_index = (self._active_match_index - 1) % len(self._matches)
        panel = self.main.search_panel
        focus_state = self._capture_focus_state()
        focus_editor = not (panel.find_input.hasFocus() or panel.replace_input.hasFocus())
        self._jump_to_match(
            self._active_match_index, focus=focus_editor, preserve_focus_state=focus_state if not focus_editor else None
        )
