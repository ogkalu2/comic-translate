from __future__ import annotations

import os
import re
from dataclasses import dataclass
from typing import Iterator, Optional, TYPE_CHECKING

from PySide6 import QtCore, QtGui
from PySide6.QtGui import QTextCursor

from modules.utils.common_utils import is_close
from app.ui.commands.search_replace import ReplaceBlocksCommand, ReplaceChange

if TYPE_CHECKING:
    from controller import ComicTranslate

# Shorthand for translations
_translate = QtCore.QCoreApplication.translate


@dataclass(frozen=True)
class BlockKey:
    file_path: str
    xyxy: tuple[int, int, int, int]
    angle: float


@dataclass(frozen=True)
class SearchOptions:
    query: str
    replace: str
    match_case: bool = False
    whole_word: bool = False
    regex: bool = False
    preserve_case: bool = False
    scope_all_images: bool = False
    in_target: bool = True


@dataclass(frozen=True)
class SearchMatch:
    key: BlockKey
    block_index_hint: int
    match_ordinal_in_block: int
    start: int
    end: int
    preview: str


def _vscode_regex_replacement_to_python(repl: str) -> str:
    """
    Best-effort conversion of VS Code-style regex replacement tokens to Python's re:
    - $1, $2 ... -> \\g<1>, \\g<2> ...
    - $& -> \\g<0>
    - ${name} -> \\g<name>
    - $$ -> $
    """
    if not repl:
        return repl
    sentinel = "\u0000"
    repl = repl.replace("$$", sentinel)
    repl = repl.replace("$&", r"\g<0>")
    repl = re.sub(r"\$\{([A-Za-z_][A-Za-z0-9_]*)\}", r"\\g<\1>", repl)
    repl = re.sub(r"\$(\d+)", r"\\g<\1>", repl)
    return repl.replace(sentinel, "$")


def _apply_preserve_case(matched_text: str, replacement: str) -> str:
    """
    Apply the case pattern of matched_text to replacement.
    
    Patterns detected:
    - all lowercase -> replacement lowercase
    - ALL UPPERCASE -> REPLACEMENT UPPERCASE  
    - Title Case / Capitalized -> Replacement Capitalized
    - First char upper, rest mixed -> First char of replacement upper
    """
    if not matched_text or not replacement:
        return replacement
    
    # Check if all lowercase
    if matched_text.islower():
        return replacement.lower()
    
    # Check if all uppercase
    if matched_text.isupper():
        return replacement.upper()
    
    # Check if title case (each word capitalized)
    if matched_text.istitle():
        return replacement.title()
    
    # Check if first character is uppercase (capitalize first only)
    if matched_text[0].isupper():
        return replacement[0].upper() + replacement[1:] if len(replacement) > 1 else replacement.upper()
    
    # Default: return replacement as-is
    return replacement


def compile_search_pattern(opts: SearchOptions) -> re.Pattern[str]:
    query = (opts.query or "").strip()
    if not query:
        raise ValueError("Empty query")

    flags = re.UNICODE
    if not opts.match_case:
        flags |= re.IGNORECASE

    if opts.regex:
        body = query
    else:
        body = re.escape(query)

    if opts.whole_word:
        body = rf"(?<!\w)(?:{body})(?!\w)"

    return re.compile(body, flags=flags)


def find_matches_in_text(text: str, pattern: re.Pattern[str]) -> list[tuple[int, int]]:
    out: list[tuple[int, int]] = []
    for m in pattern.finditer(text or ""):
        if m.start() == m.end():
            continue
        out.append((m.start(), m.end()))
    return out


def _make_preview(text: str, start: int, end: int, radius: int = 30) -> str:
    text = text or ""
    safe = text.replace("\r\n", "\n").replace("\r", "\n")
    safe = safe.replace("\n", "\\n")
    left = max(0, start - radius)
    right = min(len(safe), end + radius)
    prefix = "…" if left > 0 else ""
    suffix = "…" if right < len(safe) else ""
    return f"{prefix}{safe[left:right]}{suffix}"

def _looks_like_html(text: str) -> bool:
    if not text:
        return False
    return bool(re.search(r"<[^>]+>", text))


def _to_qt_plain(text: str) -> str:
    # QTextDocument uses U+2029 (paragraph separator) for line breaks in toPlainText().
    t = (text or "").replace("\r\n", "\n").replace("\r", "\n")
    return t.replace("\n", "\u2029")

def _qt_plain_to_user(text: str) -> str:
    return (text or "").replace("\u2029", "\n")


def _apply_replacements_to_html(
    existing_html: str,
    pattern: re.Pattern[str],
    replacement: str,
    *,
    regex_mode: bool,
    preserve_case: bool = False,
    nth: int | None = None,
) -> tuple[str, str, str, int]:
    """
    Apply replacements directly to a QTextDocument created from existing HTML to preserve rich formatting.
    Returns (old_plain, new_plain, new_html, count).
    """
    doc = QtGui.QTextDocument()
    if _looks_like_html(existing_html):
        doc.setHtml(existing_html)
    else:
        doc.setPlainText(existing_html or "")

    old_plain = _qt_plain_to_user(doc.toPlainText())
    matches = [m for m in pattern.finditer(old_plain) if m.start() != m.end()]
    if nth is not None:
        if nth < 0 or nth >= len(matches):
            return old_plain, old_plain, doc.toHtml(), 0
        matches = [matches[nth]]

    if not matches:
        return old_plain, old_plain, doc.toHtml(), 0

    py_repl = _vscode_regex_replacement_to_python(replacement) if regex_mode else replacement

    for m in reversed(matches):
        start, end = m.start(), m.end()
        try:
            repl_text = m.expand(py_repl) if regex_mode else py_repl
        except Exception:
            repl_text = py_repl if isinstance(py_repl, str) else ""
        
        # Apply preserve case if enabled
        if preserve_case:
            matched_text = old_plain[start:end]
            repl_text = _apply_preserve_case(matched_text, repl_text)

        fmt_cur = QTextCursor(doc)
        fmt_cur.setPosition(start)
        fmt = fmt_cur.charFormat()

        cursor = QTextCursor(doc)
        cursor.setPosition(start)
        cursor.setPosition(end, QTextCursor.KeepAnchor)
        cursor.beginEditBlock()
        cursor.removeSelectedText()
        cursor.insertText(_to_qt_plain(repl_text), fmt)
        cursor.endEditBlock()

    new_html = doc.toHtml()
    new_plain = _qt_plain_to_user(doc.toPlainText())
    return old_plain, new_plain, new_html, len(matches)

def _rect_area(r: QtCore.QRectF) -> float:
    return max(0.0, float(r.width())) * max(0.0, float(r.height()))


def _apply_text_delta_to_document(doc: QtGui.QTextDocument, new_text: str) -> bool:
    old_text = doc.toPlainText()
    new_text_qt = _to_qt_plain(new_text)
    if old_text == new_text_qt:
        return False

    prefix = 0
    max_prefix = min(len(old_text), len(new_text_qt))
    while prefix < max_prefix and old_text[prefix] == new_text_qt[prefix]:
        prefix += 1

    suffix = 0
    max_suffix = min(len(old_text) - prefix, len(new_text_qt) - prefix)
    while suffix < max_suffix and old_text[-(suffix + 1)] == new_text_qt[-(suffix + 1)]:
        suffix += 1

    old_mid_end = len(old_text) - suffix
    new_mid_end = len(new_text_qt) - suffix
    old_mid = old_text[prefix:old_mid_end]
    new_mid = new_text_qt[prefix:new_mid_end]

    cursor = QTextCursor(doc)
    insert_format = None
    if old_text:
        if prefix < len(old_text):
            cursor.setPosition(prefix)
            insert_format = cursor.charFormat()
        elif prefix > 0:
            cursor.setPosition(prefix - 1)
            insert_format = cursor.charFormat()

    cursor.beginEditBlock()
    if old_mid:
        cursor.setPosition(prefix)
        cursor.setPosition(prefix + len(old_mid), QTextCursor.KeepAnchor)
        cursor.removeSelectedText()
    if new_mid:
        cursor.setPosition(prefix)
        if insert_format is not None:
            cursor.setCharFormat(insert_format)
        cursor.insertText(new_mid)
    cursor.endEditBlock()
    return True


def replace_nth_match(
    text: str,
    pattern: re.Pattern[str],
    replacement: str,
    n: int,
    regex_mode: bool,
) -> tuple[str, bool]:
    """
    Replace only the nth match in `text` (0-based). Returns (new_text, replaced?).
    """
    if n < 0:
        return text, False
    matches = list(pattern.finditer(text or ""))
    matches = [m for m in matches if m.start() != m.end()]
    if n >= len(matches):
        return text, False
    m = matches[n]
    if regex_mode:
        py_repl = _vscode_regex_replacement_to_python(replacement)
        repl_text = m.expand(py_repl)
    else:
        repl_text = replacement
    return (text[: m.start()] + repl_text + text[m.end() :], True)


def replace_all_matches(
    text: str,
    pattern: re.Pattern[str],
    replacement: str,
    regex_mode: bool,
    preserve_case: bool = False,
) -> tuple[str, int]:
    if regex_mode:
        py_repl = _vscode_regex_replacement_to_python(replacement)
        if preserve_case:
            def repl_func(m):
                expanded = m.expand(py_repl)
                return _apply_preserve_case(m.group(0), expanded)
            new_text, count = pattern.subn(repl_func, text or "")
        else:
            new_text, count = pattern.subn(py_repl, text or "")
        return new_text, count
    
    if preserve_case:
        def repl_func(m):
            return _apply_preserve_case(m.group(0), replacement)
        new_text, count = pattern.subn(repl_func, text or "")
    else:
        new_text, count = pattern.subn(lambda _m: replacement, text or "")
    return new_text, count


class SearchReplaceController(QtCore.QObject):
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
            return _translate("SearchReplaceController", "Empty query")
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
            panel.set_status(_translate('SearchReplaceController', 'Search Error') + ": " + self._format_pattern_error(e))
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
                key = BlockKey(
                    file_path=file_path,
                    xyxy=(int(blk.xyxy[0]), int(blk.xyxy[1]), int(blk.xyxy[2]), int(blk.xyxy[3])),
                    angle=float(getattr(blk, "angle", 0.0) or 0.0),
                )
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
            panel.set_status(_translate("SearchReplaceController", "Ready"))
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
            panel.set_status(_translate("SearchReplaceController", "No results"))

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

    def _set_current_row_for_file(self, file_path: str) -> bool:
        try:
            idx = self.main.image_files.index(file_path)
        except ValueError:
            return False
        if self.main.curr_img_idx == idx:
            return True
        # This triggers ImageStateController.on_card_selected and loads the image/state asynchronously.
        self.main.page_list.setCurrentRow(idx)
        return True

    def _find_block_in_current_image(self, key: BlockKey) -> Optional[object]:
        if self.main.curr_img_idx < 0:
            return None
        current_file = self.main.image_files[self.main.curr_img_idx]
        if os.path.normcase(current_file) != os.path.normcase(key.file_path):
            return None

        def _key_xyxy_to_scene() -> tuple[float, float, float, float] | None:
            if not getattr(self.main, "webtoon_mode", False):
                return None
            viewer = getattr(self.main, "image_viewer", None)
            webtoon_manager = getattr(viewer, "webtoon_manager", None) if viewer is not None else None
            converter = getattr(webtoon_manager, "coordinate_converter", None) if webtoon_manager is not None else None
            if converter is None:
                return None
            try:
                page_idx = self.main.image_files.index(key.file_path)
            except ValueError:
                return None
            try:
                tl = QtCore.QPointF(float(key.xyxy[0]), float(key.xyxy[1]))
                br = QtCore.QPointF(float(key.xyxy[2]), float(key.xyxy[3]))
                stl = converter.page_local_to_scene_position(tl, page_idx)
                sbr = converter.page_local_to_scene_position(br, page_idx)
                return (float(stl.x()), float(stl.y()), float(sbr.x()), float(sbr.y()))
            except Exception:
                return None

        scene_xyxy = _key_xyxy_to_scene()
        for blk in self.main.blk_list or []:
            angle = float(getattr(blk, "angle", 0.0) or 0.0)
            try:
                bxyxy = (float(blk.xyxy[0]), float(blk.xyxy[1]), float(blk.xyxy[2]), float(blk.xyxy[3]))
            except Exception:
                continue

            # Exact match (regular mode / already-scene keys)
            if (
                (int(bxyxy[0]), int(bxyxy[1]), int(bxyxy[2]), int(bxyxy[3])) == key.xyxy
                and is_close(angle, key.angle, 0.5)
            ):
                return blk

            # Webtoon mode: keys commonly come from per-page stored state (page-local coords),
            # while loaded blocks in main.blk_list use scene coords.
            if scene_xyxy is not None and is_close(angle, key.angle, 0.5):
                if (
                    is_close(bxyxy[0], scene_xyxy[0], 5)
                    and is_close(bxyxy[1], scene_xyxy[1], 5)
                    and is_close(bxyxy[2], scene_xyxy[2], 5)
                    and is_close(bxyxy[3], scene_xyxy[3], 5)
                ):
                    return blk
        return None

    def _find_text_item_for_block(self, blk: object):
        if not getattr(self.main, "image_viewer", None):
            return None
        text_items = getattr(self.main.image_viewer, "text_items", None)
        if not text_items:
            return None
        try:
            x1, y1, x2, y2 = blk.xyxy
        except Exception:
            return None

        block_rect = QtCore.QRectF(float(x1), float(y1), float(x2 - x1), float(y2 - y1))
        block_area = _rect_area(block_rect)
        if block_area <= 0:
            return None

        best = None
        best_score = 0.0
        for item in text_items:
            try:
                item_rect = item.mapToScene(item.boundingRect()).boundingRect()
            except Exception:
                continue
            if not block_rect.intersects(item_rect):
                continue
            inter = block_rect.intersected(item_rect)
            inter_area = _rect_area(inter)
            if inter_area <= 0:
                continue
            score = inter_area / max(1e-6, min(block_area, _rect_area(item_rect)))
            if score > best_score:
                best_score = score
                best = item

        # Require a modest overlap so we don't accidentally select unrelated text items.
        if best is not None and best_score >= 0.15:
            return best
        return None

    def _select_block(self, blk: object):
        # Prefer selecting a rendered TextBlockItem if available.
        try:
            text_item = self._find_text_item_for_block(blk)
            if text_item is not None:
                self.main.image_viewer.deselect_all()
                text_item.selected = True
                text_item.setSelected(True)
                try:
                    if not getattr(text_item, "editing_mode", False):
                        text_item.item_selected.emit(text_item)
                except Exception:
                    pass
                try:
                    self.main.image_viewer.centerOn(text_item)
                except Exception:
                    pass
                return
        except Exception:
            pass

        try:
            rect = self.main.rect_item_ctrl.find_corresponding_rect(blk, 0.2)
            if rect:
                self.main.image_viewer.select_rectangle(rect)
                return
        except Exception:
            pass

        # Fallback: update text edits only.
        try:
            self.main.curr_tblock = blk
            self.main.s_text_edit.blockSignals(True)
            self.main.t_text_edit.blockSignals(True)
            self.main.s_text_edit.setPlainText(getattr(blk, "text", "") or "")
            self.main.t_text_edit.setPlainText(getattr(blk, "translation", "") or "")
            self.main.s_text_edit.blockSignals(False)
            self.main.t_text_edit.blockSignals(False)
        except Exception:
            pass

    def _highlight_in_target_edit(self, start: int, end: int):
        try:
            edit = self.main.t_text_edit
            cursor = edit.textCursor()
            cursor.setPosition(start)
            cursor.setPosition(end, QTextCursor.KeepAnchor)
            edit.setTextCursor(cursor)
            edit.ensureCursorVisible()
        except Exception:
            pass

    def _highlight_in_source_edit(self, start: int, end: int):
        try:
            edit = self.main.s_text_edit
            cursor = edit.textCursor()
            cursor.setPosition(start)
            cursor.setPosition(end, QTextCursor.KeepAnchor)
            edit.setTextCursor(cursor)
            edit.ensureCursorVisible()
        except Exception:
            pass

    def _apply_match_selection(self, m: SearchMatch, blk: object, focus: bool, preserve_focus_state=None):
        self._select_block(blk)
        if self._gather_options().in_target:
            self._highlight_in_target_edit(m.start, m.end)
            if focus:
                self.main.t_text_edit.setFocus()
        else:
            self._highlight_in_source_edit(m.start, m.end)
            if focus:
                self.main.s_text_edit.setFocus()
        if preserve_focus_state is not None and not focus:
            self._restore_focus_state(preserve_focus_state)

    def _apply_webtoon_fallback_selection(self, m: SearchMatch, focus: bool, preserve_focus_state=None):
        # Webtoon mode: if the page hasn't loaded into the scene yet, fall back to the
        # page's stored blk_list to at least populate the MTPE edits.
        state = self.main.image_states.get(m.key.file_path) or {}
        blks = state.get("blk_list") or []
        blk = next(
            (
                b
                for b in blks
                if (int(b.xyxy[0]), int(b.xyxy[1]), int(b.xyxy[2]), int(b.xyxy[3])) == m.key.xyxy
                and is_close(float(getattr(b, "angle", 0.0) or 0.0), m.key.angle, 0.5)
            ),
            None,
        )
        if blk is None:
            return
        self._select_block(blk)
        if self._gather_options().in_target:
            self._highlight_in_target_edit(m.start, m.end)
            if focus:
                self.main.t_text_edit.setFocus()
        else:
            self._highlight_in_source_edit(m.start, m.end)
            if focus:
                self.main.s_text_edit.setFocus()
        if preserve_focus_state is not None and not focus:
            self._restore_focus_state(preserve_focus_state)

    def _wait_for_webtoon_match_loaded(
        self,
        match_index: int,
        focus: bool,
        *,
        attempt_load: int,
        preserve_focus_state=None,
        nonce: int | None = None,
    ):
        if nonce is not None and nonce != self._jump_nonce:
            return
        if match_index < 0 or match_index >= len(self._matches):
            return
        m = self._matches[match_index]

        blk = self._find_block_in_current_image(m.key)
        if blk is not None:
            self._apply_match_selection(m, blk, focus, preserve_focus_state)
            return

        if attempt_load >= 35:  # ~2s (35 * 60ms)
            self._apply_webtoon_fallback_selection(m, focus, preserve_focus_state)
            return

        QtCore.QTimer.singleShot(
            60,
            lambda: self._wait_for_webtoon_match_loaded(
                match_index,
                focus,
                attempt_load=attempt_load + 1,
                preserve_focus_state=preserve_focus_state,
                nonce=nonce,
            ),
        )

    def _jump_to_match_when_ready(
        self, match_index: int, focus: bool, attempt: int = 0, preserve_focus_state=None, nonce: int | None = None
    ):
        if nonce is not None and nonce != self._jump_nonce:
            return
        if match_index < 0 or match_index >= len(self._matches):
            return
        m = self._matches[match_index]

        # In regular mode, page switches load asynchronously. Wait until current index matches.
        if self.main.curr_img_idx < 0:
            if attempt > 50:
                return
            QtCore.QTimer.singleShot(
                60, lambda: self._jump_to_match_when_ready(match_index, focus, attempt + 1, nonce=nonce)
            )
            return

        current_file = self.main.image_files[self.main.curr_img_idx] if self.main.image_files else ""
        if os.path.normcase(current_file) != os.path.normcase(m.key.file_path):
            if attempt > 50:
                return
            QtCore.QTimer.singleShot(
                60,
                lambda: self._jump_to_match_when_ready(
                    match_index, focus, attempt + 1, preserve_focus_state, nonce=nonce
                ),
            )
            return

        blk = self._find_block_in_current_image(m.key)
        if blk is None:
            if getattr(self.main, "webtoon_mode", False):
                # Wait for the target page's scene items (text/rectangles/blocks) to load, then select.
                self._wait_for_webtoon_match_loaded(
                    match_index, focus, attempt_load=0, preserve_focus_state=preserve_focus_state, nonce=nonce
                )
                return

            if attempt > 50:
                return
            QtCore.QTimer.singleShot(
                60,
                lambda: self._jump_to_match_when_ready(
                    match_index, focus, attempt + 1, preserve_focus_state, nonce=nonce
                ),
            )
            return

        self._apply_match_selection(m, blk, focus, preserve_focus_state)

    def _jump_to_match(self, match_index: int, focus: bool = False, preserve_focus_state=None):
        if match_index < 0 or match_index >= len(self._matches):
            return
        m = self._matches[match_index]
        panel = self.main.search_panel
        panel.select_match(m)

        if not self._set_current_row_for_file(m.key.file_path):
            return
        self._jump_nonce += 1
        nonce = self._jump_nonce
        self._jump_to_match_when_ready(match_index, focus, attempt=0, preserve_focus_state=preserve_focus_state, nonce=nonce)

    def _on_result_activated(self, match: SearchMatch):
        try:
            idx = self._matches.index(match)
        except ValueError:
            idx = -1
        if idx >= 0:
            self._active_match_index = idx
        self._jump_to_match(self._active_match_index, focus=True)

    def _apply_block_text(self, opts: SearchOptions, key: BlockKey, new_text: str):
        return self._apply_block_text_with_html(opts, key, new_text, html_override=None)

    def _find_matching_text_item_state(self, state: dict, key: BlockKey) -> Optional[dict]:
        viewer_state = state.get("viewer_state") or {}
        text_items_state = viewer_state.get("text_items_state") or []
        for ti in text_items_state:
            pos = ti.get("position") or (None, None)
            rot = float(ti.get("rotation") or 0.0)
            if pos[0] is None:
                continue
            if (
                is_close(float(pos[0]), float(key.xyxy[0]), 5)
                and is_close(float(pos[1]), float(key.xyxy[1]), 5)
                and is_close(rot, key.angle, 1.0)
            ):
                return ti
        return None

    def _apply_block_text_with_html(
        self, opts: SearchOptions, key: BlockKey, new_text: str, *, html_override: str | None
    ):
        state = self.main.image_states.get(key.file_path)
        if state:
            blks = state.get("blk_list") or []
            for blk in blks:
                xyxy = (int(blk.xyxy[0]), int(blk.xyxy[1]), int(blk.xyxy[2]), int(blk.xyxy[3]))
                angle = float(getattr(blk, "angle", 0.0) or 0.0)
                if xyxy == key.xyxy and is_close(angle, key.angle, 0.5):
                    if opts.in_target:
                        blk.translation = new_text
                    else:
                        blk.text = new_text
                    break

            # Keep persisted rendered text items in sync so switching pages doesn't resurrect old text.
            if opts.in_target:
                ti = self._find_matching_text_item_state(state, key)
                if ti is not None:
                    if html_override is not None:
                        ti["text"] = html_override
                    else:
                        existing = ti.get("text") or ""
                        if _looks_like_html(existing):
                            try:
                                doc = QtGui.QTextDocument()
                                doc.setHtml(existing)
                                if _apply_text_delta_to_document(doc, new_text):
                                    ti["text"] = doc.toHtml()
                            except Exception:
                                pass
                        else:
                            ti["text"] = new_text

        # If currently displayed, update canvas + edits as well.
        blk = self._find_block_in_current_image(key)
        if blk is None:
            return

        if opts.in_target:
            blk.translation = new_text
        else:
            blk.text = new_text

        if opts.in_target:
            # If there's a rendered TextBlockItem corresponding to this block, keep it in sync.
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

        # If the selected edits are this block, reflect the new text.
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
        except Exception as e:
            panel.set_status(_translate('SearchReplaceController', 'Replace Error') + ": " + self._format_pattern_error(e))
            return

        m = self._matches[self._active_match_index]
        old_html = None
        new_html = None

        # If the page has a persisted TextBlockItem state (rich text), update it in-place to preserve formatting.
        state = self.main.image_states.get(m.key.file_path) or {}
        if opts.in_target:
            ti = self._find_matching_text_item_state(state, m.key)
            existing_html = (ti.get("text") if ti else None) if isinstance(ti, dict) else None
            if isinstance(existing_html, str) and existing_html:
                old_text, new_text, new_html, count = _apply_replacements_to_html(
                    existing_html,
                    pattern,
                    opts.replace,
                    regex_mode=opts.regex,
                    preserve_case=opts.preserve_case,
                    nth=m.match_ordinal_in_block,
                )
                if count <= 0 or new_text == old_text:
                    return
                old_html = existing_html
            else:
                old_text = None
                new_text = None
        else:
            old_text = None
            new_text = None

        if old_text is None:
            # Prefer the currently loaded block (so Replace works even when state isn't up to date).
            target_blk = self._find_block_in_current_image(m.key)
            if target_blk is None:
                blks = state.get("blk_list") or []
                target_blk = next(
                    (
                        blk
                        for blk in blks
                        if (int(blk.xyxy[0]), int(blk.xyxy[1]), int(blk.xyxy[2]), int(blk.xyxy[3])) == m.key.xyxy
                        and is_close(float(getattr(blk, "angle", 0.0) or 0.0), m.key.angle, 0.5)
                    ),
                    None,
                )
            if target_blk is None:
                return
            old_text = target_blk.translation if opts.in_target else target_blk.text
            new_text, changed = replace_nth_match(
                old_text, pattern, opts.replace, m.match_ordinal_in_block, regex_mode=opts.regex
            )
            if not changed or new_text == old_text:
                return

        stack = self.main.undo_group.activeStack()
        if stack:
            cmd = ReplaceBlocksCommand(
                self,
                in_target=opts.in_target,
                changes=[
                    ReplaceChange(
                        file_path=m.key.file_path,
                        xyxy=m.key.xyxy,
                        angle=m.key.angle,
                        old_text=old_text,
                        new_text=new_text,
                        old_html=old_html,
                        new_html=new_html,
                    )
                ],
                text=_translate("SearchReplaceController", "Replace"),
            )
            stack.push(cmd)
        else:
            self._apply_block_text_with_html(opts, m.key, new_text, html_override=new_html)
        panel.set_status(_translate("SearchReplaceController", "Replaced 1 occurrence(s)"))
        self.search()

    def replace_all(self):
        panel = self.main.search_panel
        opts = self._gather_options()
        try:
            pattern = compile_search_pattern(opts)
        except Exception as e:
            panel.set_status(_translate('SearchReplaceController', 'Replace Error') + ": " + self._format_pattern_error(e))
            return

        total_replacements = 0
        changes: list[ReplaceChange] = []

        for file_path, _blk_list, _idx, blk in self._iter_blocks(opts) or []:
            key = BlockKey(
                file_path=file_path,
                xyxy=(int(blk.xyxy[0]), int(blk.xyxy[1]), int(blk.xyxy[2]), int(blk.xyxy[3])),
                angle=float(getattr(blk, "angle", 0.0) or 0.0),
            )

            old_html = None
            new_html = None

            state = self.main.image_states.get(file_path) or {}
            if opts.in_target:
                ti = self._find_matching_text_item_state(state, key)
                existing_html = (ti.get("text") if ti else None) if isinstance(ti, dict) else None
                if isinstance(existing_html, str) and existing_html:
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
                    old_html = existing_html
                else:
                    old_text = blk.translation
                    new_text, count = replace_all_matches(
                        old_text, pattern, opts.replace,
                        regex_mode=opts.regex, preserve_case=opts.preserve_case
                    )
                    if count <= 0 or new_text == old_text:
                        continue
            else:
                old_text = blk.text
                new_text, count = replace_all_matches(
                    old_text, pattern, opts.replace,
                    regex_mode=opts.regex, preserve_case=opts.preserve_case
                )
                if count <= 0 or new_text == old_text:
                    continue

            total_replacements += count
            changes.append(
                ReplaceChange(
                    file_path=key.file_path,
                    xyxy=key.xyxy,
                    angle=key.angle,
                    old_text=old_text,
                    new_text=new_text,
                    old_html=old_html,
                    new_html=new_html,
                )
            )

        if changes:
            stack = self.main.undo_group.activeStack()
            if stack:
                cmd = ReplaceBlocksCommand(
                    self,
                    in_target=opts.in_target,
                    changes=changes,
                    text=_translate("SearchReplaceController", "Replace All"),
                )
                stack.push(cmd)
            else:
                for ch in changes:
                    self._apply_block_text(opts, ch.key, ch.new_text)

        if total_replacements:
            panel.set_status(_translate("SearchReplaceController", "Replaced {0} occurrence(s)").format(total_replacements))
        else:
            panel.set_status(_translate("SearchReplaceController", "No replacements"))

        self.search()
