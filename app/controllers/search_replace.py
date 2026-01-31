from __future__ import annotations

import os
import re
from dataclasses import dataclass
from typing import Iterable, Iterator, Optional

from PySide6 import QtCore, QtGui
from PySide6.QtGui import QTextCursor

from modules.utils.common_utils import is_close
from app.ui.commands.search_replace import ReplaceBlocksCommand, ReplaceChange


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
) -> tuple[str, int]:
    if regex_mode:
        py_repl = _vscode_regex_replacement_to_python(replacement)
        new_text, count = pattern.subn(py_repl, text or "")
        return new_text, count
    new_text, count = pattern.subn(lambda _m: replacement, text or "")
    return new_text, count


class SearchReplaceController(QtCore.QObject):
    def __init__(self, main):
        super().__init__(main)
        self.main = main
        self._matches: list[SearchMatch] = []
        self._active_match_index: int = -1

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
        QtGui.QShortcut(QtGui.QKeySequence("F3"), self.main, activated=self.next_match)
        QtGui.QShortcut(QtGui.QKeySequence("Shift+F3"), self.main, activated=self.prev_match)

    def focus_find(self):
        panel = self.main.search_panel
        panel.find_input.setFocus()
        panel.find_input.selectAll()

    def focus_replace(self):
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
            scope_all_images=(panel.scope_combo.currentData() == "all"),
            in_target=(panel.field_combo.currentData() == "target"),
        )

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
            if self.main.curr_img_idx < 0:
                return
            file_path = self.main.image_files[self.main.curr_img_idx]
            for idx, blk in enumerate(self.main.blk_list or []):
                yield file_path, self.main.blk_list, idx, blk
            return

        # Ensure current image edits are persisted into image_states.viewer_state when possible.
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
            panel.set_status(f"{self.main.tr('Search error')}: {e}")
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
            panel.set_status(self.main.tr("Ready"))
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
            panel.set_status(self.main.tr("No results"))

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

        for blk in self.main.blk_list or []:
            xyxy = (int(blk.xyxy[0]), int(blk.xyxy[1]), int(blk.xyxy[2]), int(blk.xyxy[3]))
            angle = float(getattr(blk, "angle", 0.0) or 0.0)
            if xyxy == key.xyxy and is_close(angle, key.angle, 0.5):
                return blk
        return None

    def _select_block(self, blk: object):
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

    def _jump_to_match_when_ready(self, match_index: int, focus: bool, attempt: int = 0, preserve_focus_state=None):
        if match_index < 0 or match_index >= len(self._matches):
            return
        m = self._matches[match_index]

        # In regular mode, page switches load asynchronously. Wait until current index matches.
        if self.main.curr_img_idx < 0:
            if attempt > 50:
                return
            QtCore.QTimer.singleShot(60, lambda: self._jump_to_match_when_ready(match_index, focus, attempt + 1))
            return

        current_file = self.main.image_files[self.main.curr_img_idx] if self.main.image_files else ""
        if os.path.normcase(current_file) != os.path.normcase(m.key.file_path):
            if attempt > 50:
                return
            QtCore.QTimer.singleShot(
                60, lambda: self._jump_to_match_when_ready(match_index, focus, attempt + 1, preserve_focus_state)
            )
            return

        blk = self._find_block_in_current_image(m.key)
        if blk is None:
            # In webtoon mode we don't always load per-page blk_list into main.blk_list.
            # Fall back to the page's stored blk_list to at least populate the MTPE edits.
            if getattr(self.main, "webtoon_mode", False):
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
                if blk is not None:
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
                    return

            if attempt > 50:
                return
            QtCore.QTimer.singleShot(
                60, lambda: self._jump_to_match_when_ready(match_index, focus, attempt + 1, preserve_focus_state)
            )
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

    def _jump_to_match(self, match_index: int, focus: bool = False, preserve_focus_state=None):
        if match_index < 0 or match_index >= len(self._matches):
            return
        m = self._matches[match_index]
        panel = self.main.search_panel
        panel.select_match(m)

        if not self._set_current_row_for_file(m.key.file_path):
            return
        self._jump_to_match_when_ready(match_index, focus, attempt=0, preserve_focus_state=preserve_focus_state)

    def _on_result_activated(self, match: SearchMatch):
        try:
            idx = self._matches.index(match)
        except ValueError:
            idx = -1
        if idx >= 0:
            self._active_match_index = idx
        self._jump_to_match(self._active_match_index, focus=True)

    def _apply_block_text(self, opts: SearchOptions, key: BlockKey, new_text: str):
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

            # Best-effort: if the page has persisted rendered text items in viewer_state,
            # keep them in sync so switching pages doesn't resurrect old text.
            viewer_state = state.get("viewer_state") or {}
            text_items_state = viewer_state.get("text_items_state") or []
            if opts.in_target:
                try:
                    doc = QtGui.QTextDocument()
                    doc.setPlainText(new_text)
                    new_html = doc.toHtml()
                except Exception:
                    new_html = new_text
                for ti in text_items_state:
                    pos = ti.get("position") or (None, None)
                    rot = float(ti.get("rotation") or 0.0)
                    if pos[0] is None:
                        continue
                    if is_close(float(pos[0]), float(key.xyxy[0]), 5) and is_close(float(pos[1]), float(key.xyxy[1]), 5) and is_close(rot, key.angle, 1.0):
                        ti["text"] = new_html

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
                        self.main.text_ctrl.apply_text_from_command(text_item, new_text, html=None, blk=blk)
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
    ):
        key = BlockKey(file_path=file_path, xyxy=xyxy, angle=angle)
        opts = SearchOptions(query="", replace="", in_target=bool(in_target))
        self._apply_block_text(opts, key, new_text)

    def replace_current(self):
        if not self._matches or self._active_match_index < 0:
            return
        panel = self.main.search_panel
        opts = self._gather_options()
        try:
            pattern = compile_search_pattern(opts)
        except Exception as e:
            panel.set_status(f"{self.main.tr('Replace error')}: {e}")
            return

        m = self._matches[self._active_match_index]
        # Prefer the currently loaded block (so Replace works even when state isn't up to date).
        target_blk = self._find_block_in_current_image(m.key)
        if target_blk is None:
            state = self.main.image_states.get(m.key.file_path) or {}
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
                    )
                ],
                text=self.main.tr("Replace"),
            )
            stack.push(cmd)
        else:
            self._apply_block_text(opts, m.key, new_text)
        panel.set_status(self.main.tr("Replaced 1 occurrence(s)"))
        self.search()

    def replace_all(self):
        panel = self.main.search_panel
        opts = self._gather_options()
        try:
            pattern = compile_search_pattern(opts)
        except Exception as e:
            panel.set_status(f"{self.main.tr('Replace error')}: {e}")
            return

        total_replacements = 0
        changes: list[ReplaceChange] = []

        for file_path, _blk_list, _idx, blk in self._iter_blocks(opts) or []:
            old_text = blk.translation if opts.in_target else blk.text
            new_text, count = replace_all_matches(old_text, pattern, opts.replace, regex_mode=opts.regex)
            if count <= 0 or new_text == old_text:
                continue
            total_replacements += count
            key = BlockKey(
                file_path=file_path,
                xyxy=(int(blk.xyxy[0]), int(blk.xyxy[1]), int(blk.xyxy[2]), int(blk.xyxy[3])),
                angle=float(getattr(blk, "angle", 0.0) or 0.0),
            )
            changes.append(
                ReplaceChange(
                    file_path=key.file_path,
                    xyxy=key.xyxy,
                    angle=key.angle,
                    old_text=old_text,
                    new_text=new_text,
                )
            )

        if changes:
            stack = self.main.undo_group.activeStack()
            if stack:
                cmd = ReplaceBlocksCommand(
                    self,
                    in_target=opts.in_target,
                    changes=changes,
                    text=self.main.tr("Replace All"),
                )
                stack.push(cmd)
            else:
                for ch in changes:
                    self._apply_block_text(opts, ch.key, ch.new_text)

        if total_replacements:
            panel.set_status(self.main.tr("Replaced {0} occurrence(s)").format(total_replacements))
        else:
            panel.set_status(self.main.tr("No replacements"))

        self.search()
